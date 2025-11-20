# authentication/otp_manager.py
"""
Production-grade OTPManager
- Redis (django-redis) primary cache
- DB as fallback and audit trail
- Per-phone lock to avoid races (SETNX)
- Cache-first verify, DB fallback with caching
- Timing-safe comparisons
- Attempts counter in Redis (atomic INCR)
"""

import logging
import secrets
import re
import json
from typing import Optional, Tuple
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .models import OTP  # Assumes OTP model has id, phone_number, code, created_at, expires_at
logger = logging.getLogger(__name__)

# Optional import - best-effort: if django_redis available, use low-level redis for locking & pipeline
try:
    from django_redis import get_redis_connection
    HAS_DJANGO_REDIS = True
except Exception:
    HAS_DJANGO_REDIS = False


class OTPManager:
    OTP_LENGTH = 6
    OTP_EXPIRY_SECONDS = getattr(settings, "OTP_EXPIRY_SECONDS", 300)
    MAX_ATTEMPTS = getattr(settings, "OTP_MAX_ATTEMPTS", 3)
    COOLDOWN_SECONDS = getattr(settings, "OTP_COOLDOWN_SECONDS", 60)
    LOCK_TTL = 5  # seconds for per-phone lock

    CACHE_KEY_PREFIX = "otp:"
    ATTEMPT_KEY_PREFIX = "otp_attempts:"
    LAST_SENT_KEY_PREFIX = "otp_last_sent:"
    DB_ID_KEY_PREFIX = "otp_db_id:"
    LOCK_KEY_PREFIX = "otp_lock:"

    @staticmethod
    def normalize_phone(phone: str) -> str:
        if not phone:
            return phone
        phone = re.sub(r'[\s\-\(\)]+', '', phone)
        if not phone.startswith("+"):
            phone = "+" + phone
        return phone

    @staticmethod
    def _cache_key(phone: str) -> str:
        return f"{OTPManager.CACHE_KEY_PREFIX}{phone}"

    @staticmethod
    def _attempt_key(phone: str) -> str:
        return f"{OTPManager.ATTEMPT_KEY_PREFIX}{phone}"

    @staticmethod
    def _last_sent_key(phone: str) -> str:
        return f"{OTPManager.LAST_SENT_KEY_PREFIX}{phone}"

    @staticmethod
    def _db_id_key(phone: str) -> str:
        return f"{OTPManager.DB_ID_KEY_PREFIX}{phone}"

    @staticmethod
    def _lock_key(phone: str) -> str:
        return f"{OTPManager.LOCK_KEY_PREFIX}{phone}"

    @staticmethod
    def generate_otp() -> str:
        return ''.join(str(secrets.randbelow(10)) for _ in range(OTPManager.OTP_LENGTH))

    @classmethod
    def _acquire_lock(cls, phone: str) -> bool:
        """
        Acquire a short-lived lock using redis SETNX if available;
        fallback to cache.add (atomic in many backends).
        """
        lock_key = cls._lock_key(phone)
        try:
            if HAS_DJANGO_REDIS:
                r = get_redis_connection("default")
                # SETNX with expire
                acquired = r.set(lock_key, "1", nx=True, ex=cls.LOCK_TTL)
                return bool(acquired)
            else:
                # cache.add returns True only if key didn't exist
                return cache.add(lock_key, "1", timeout=cls.LOCK_TTL)
        except Exception as e:
            logger.exception(f"Lock acquire error for {phone}: {e}")
            return False

    @classmethod
    def _release_lock(cls, phone: str):
        try:
            lock_key = cls._lock_key(phone)
            if HAS_DJANGO_REDIS:
                r = get_redis_connection("default")
                r.delete(lock_key)
            else:
                cache.delete(lock_key)
        except Exception as e:
            logger.exception(f"Lock release error for {phone}: {e}")

    @classmethod
    def create_otp(cls, phone: str) -> Tuple[str, bool]:
        phone = cls.normalize_phone(phone)
        logger.info(f"Request create_otp for {phone}")

        # Cooldown check (last_sent)
        last_sent = cache.get(cls._last_sent_key(phone))
        if last_sent:
            elapsed = (timezone.now() - last_sent).total_seconds()
            if elapsed < cls.COOLDOWN_SECONDS:
                wait = int(cls.COOLDOWN_SECONDS - elapsed)
                logger.warning(f"Cooldown active for {phone}, wait {wait}s")
                raise ValueError(f"OTP allaqachon yuborilgan. Iltimos, {wait} soniyadan keyin qayta so'rang.")

        # Acquire per-phone lock to avoid race conditions in generation
        got_lock = cls._acquire_lock(phone)
        if not got_lock:
            # If cannot acquire lock, refuse quickly (avoids duplicate writes)
            raise ValueError("Iltimos, bir necha soniya kuting va qayta urinib ko‘ring.")

        try:
            otp_code = cls.generate_otp()
            expires_at = timezone.now() + timedelta(seconds=cls.OTP_EXPIRY_SECONDS)

            # Save to DB first under transaction (audit)
            with transaction.atomic():
                otp_obj = OTP.objects.create(
                    phone_number=phone,
                    code=otp_code,
                    expires_at=expires_at
                )

            # Now try to write to cache atomically (use redis pipeline if available)
            cache_key = cls._cache_key(phone)
            attempt_key = cls._attempt_key(phone)
            last_sent_key = cls._last_sent_key(phone)
            db_id_key = cls._db_id_key(phone)

            try:
                if HAS_DJANGO_REDIS:
                    r = get_redis_connection("default")
                    # Use pipeline to set multiple keys atomically
                    pipe = r.pipeline()
                    pipe.set(cache_key, otp_code, ex=cls.OTP_EXPIRY_SECONDS)
                    pipe.set(attempt_key, 0, ex=cls.OTP_EXPIRY_SECONDS)
                    pipe.set(last_sent_key, int(timezone.now().timestamp()), ex=cls.OTP_EXPIRY_SECONDS)
                    pipe.set(db_id_key, int(otp_obj.id), ex=cls.OTP_EXPIRY_SECONDS)
                    pipe.execute()
                else:
                    cache.set(cache_key, otp_code, timeout=cls.OTP_EXPIRY_SECONDS)
                    cache.set(attempt_key, 0, timeout=cls.OTP_EXPIRY_SECONDS)
                    cache.set(last_sent_key, timezone.now(), timeout=cls.OTP_EXPIRY_SECONDS)
                    cache.set(db_id_key, otp_obj.id, timeout=cls.OTP_EXPIRY_SECONDS)
            except Exception as e:
                # Cache write failed - still OK because DB has the record.
                logger.exception(f"Cache write failed for {phone}, DB contains OTP id {otp_obj.id}: {e}")
                # We don't raise; rely on DB fallback in verify

            logger.info(f"OTP created for {phone} (db_id={otp_obj.id})")
            return otp_code, True

        finally:
            cls._release_lock(phone)

    @classmethod
    def verify_otp(cls, phone: str, code: str) -> Tuple[bool, str]:
        phone = cls.normalize_phone(phone)
        code = (code or "").strip()
        logger.info(f"Verifying OTP for {phone}")

        cache_key = cls._cache_key(phone)
        attempt_key = cls._attempt_key(phone)

        # First: atomic get attempts and maybe increment on wrong code (using redis if possible)
        try:
            # Try cache-first path
            cached = cache.get(cache_key)
        except Exception as e:
            logger.exception(f"Cache read error for {phone}: {e}")
            cached = None

        # Helper to increment attempts safely
        def incr_attempts():
            try:
                if HAS_DJANGO_REDIS:
                    r = get_redis_connection("default")
                    val = r.incr(attempt_key)
                    r.expire(attempt_key, cls.OTP_EXPIRY_SECONDS)
                    return int(val)
                else:
                    cur = cache.get(attempt_key, 0) or 0
                    cur += 1
                    cache.set(attempt_key, cur, timeout=cls.OTP_EXPIRY_SECONDS)
                    return cur
            except Exception as e:
                logger.exception(f"Attempt increment failed for {phone}: {e}")
                return 0

        # If cache present, verify directly (fast path)
        if cached is not None:
            logger.debug(f"Cache hit for {phone}")
            if secrets.compare_digest(str(cached), str(code)):
                # success -> cleanup only the specific OTP
                cls._cleanup_specific_otp(phone)
                logger.info(f"OTP verified (cache) for {phone}")
                return True, "OTP tasdiqlandi!"
            else:
                attempts = incr_attempts()
                remaining = max(cls.MAX_ATTEMPTS - attempts, 0)
                logger.warning(f"Wrong OTP (cache) for {phone}. Attempts: {attempts}/{cls.MAX_ATTEMPTS}")
                if attempts >= cls.MAX_ATTEMPTS:
                    cls._cleanup_specific_otp(phone)
                    return False, "Maksimal urinishlar soni tugadi. Iltimos, yangi OTP so'rang."
                return False, f"Noto'g'ri kod. Qolgan urinishlar: {remaining}"

        # Cache miss -> fallback to DB
        logger.debug(f"Cache miss for {phone}, checking DB fallback")
        try:
            otp_obj = OTP.objects.filter(
                phone_number=phone,
                expires_at__gt=timezone.now()
            ).order_by('-created_at').first()

            if not otp_obj:
                logger.warning(f"No valid OTP in DB for {phone}")
                return False, "OTP topilmadi yoki muddati tugagan. Iltimos, yangi OTP so'rang."

            # Populate cache with DB value for faster subsequent verifies
            try:
                cache.set(cache_key, otp_obj.code, timeout=cls.OTP_EXPIRY_SECONDS)
                cache.set(attempt_key, 0, timeout=cls.OTP_EXPIRY_SECONDS)
                cache.set(cls._db_id_key(phone), otp_obj.id, timeout=cls.OTP_EXPIRY_SECONDS)
            except Exception:
                logger.exception(f"Failed to warm cache for {phone} from DB")

            if secrets.compare_digest(str(otp_obj.code), str(code)):
                # success: delete specific DB record and cleanup cache keys
                cls._cleanup_specific_otp(phone, otp_obj_id=otp_obj.id)
                logger.info(f"OTP verified (DB fallback) for {phone}")
                return True, "OTP tasdiqlandi!"
            else:
                attempts = incr_attempts()
                remaining = max(cls.MAX_ATTEMPTS - attempts, 0)
                logger.warning(f"Wrong OTP (DB fallback) for {phone}. Attempts: {attempts}/{cls.MAX_ATTEMPTS}")
                if attempts >= cls.MAX_ATTEMPTS:
                    cls._cleanup_specific_otp(phone)
                    return False, "Maksimal urinishlar soni tugadi. Iltimos, yangi OTP so'rang."
                return False, f"Noto'g'ri kod. Qolgan urinishlar: {remaining}"

        except Exception as e:
            logger.exception(f"DB error while verifying OTP for {phone}: {e}")
            return False, "Server xatolik. Iltimos, qayta urinib ko‘ring."

    @classmethod
    def _cleanup_specific_otp(cls, phone: str, otp_obj_id: Optional[int] = None):
        """
        Clean up only specific keys and the specific DB OTP (if id provided).
        This avoids deleting other concurrent OTPs for the same phone (audit).
        """
        phone = cls.normalize_phone(phone)
        cache_key = cls._cache_key(phone)
        attempt_key = cls._attempt_key(phone)
        last_sent_key = cls._last_sent_key(phone)
        db_id_key = cls._db_id_key(phone)

        # Delete cache keys
        try:
            cache.delete(cache_key)
            cache.delete(attempt_key)
            cache.delete(last_sent_key)
            cache.delete(db_id_key)
        except Exception as e:
            logger.exception(f"Cache cleanup error for {phone}: {e}")

        # Delete DB record(s) carefully
        try:
            if otp_obj_id:
                OTP.objects.filter(id=otp_obj_id).delete()
            else:
                # If id not provided, remove only recently created ones (short window)
                cutoff = timezone.now() - timedelta(seconds=cls.OTP_EXPIRY_SECONDS + 5)
                # delete only non-expired OTPs created within window to avoid erasing historical records
                OTP.objects.filter(phone_number=phone, created_at__gt=cutoff).delete()
        except Exception as e:
            logger.exception(f"DB cleanup error for {phone}: {e}")

        logger.info(f"Cleanup specific OTP done for {phone}")
