# 📱 Medmapp WebSocket & Chat API - Frontend Developer Guide

> **Base URL:** `https://admin.medmapp.uz`  
> **WebSocket URL:** `wss://admin.medmapp.uz/ws/chat/{conversation_id}/?token={jwt_token}`  
> **Versiya:** v1.0 | **Yangilangan:** 2026-01-06

---

## 📋 Umumiy Arxitektura

```
┌─────────────────────────────────────────────────────────────┐
│                      FRONTEND APP                           │
└─────────────────────────────────────────────────────────────┘
           │                              │
           │ REST API                     │ WebSocket
           │ (CRUD operatsiyalar)         │ (Real-time xabarlar)
           ▼                              ▼
┌───────────────────────┐     ┌───────────────────────────────┐
│ /api/conversations/   │     │ wss://.../ws/chat/{id}/       │
│ /api/messages/        │     │ (doimiy ulanish)              │
└───────────────────────┘     └───────────────────────────────┘
```

---

## 🔐 1. Autentifikatsiya

### JWT Token Olish

```http
POST /api/token/
Content-Type: application/json

{
  "phone": "+998901234567",
  "password": "your_password"
}
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

### Tokenni Barcha So'rovlarga Qo'shish

```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGci...
```

---

## 💬 2. Conversations (Suhbatlar) API

### 2.1 Suhbatlar Ro'yxatini Olish

```http
GET /api/conversations/
Authorization: Bearer {token}
```

**Response:**
```json
{
  "count": 5,
  "results": [
    {
      "id": 1,
      "title": "Suhbat #1",
      "patient": {
        "id": 10,
        "full_name": "Ali Valiyev",
        "phone": "+998901234567"
      },
      "operator": {
        "id": 2,
        "full_name": "Dr. Komil"
      },
      "status": "in_progress",
      "is_active": true,
      "last_message_at": "2026-01-06T10:30:00Z",
      "unread_count": 3
    }
  ]
}
```

### 2.2 Yangi Suhbat Yaratish

```http
POST /api/conversations/
Authorization: Bearer {token}
Content-Type: application/json

{
  "patient": 10,
  "title": "Konsultatsiya - Bosh og'rig'i"
}
```

### 2.3 Suhbat Xabarlarini Olish (Pagination)

```http
GET /api/conversations/{id}/messages/?page=1
Authorization: Bearer {token}
```

**Response:**
```json
{
  "count": 50,
  "next": "/api/conversations/1/messages/?page=2",
  "previous": null,
  "results": [
    {
      "id": 101,
      "sender": {
        "id": 10,
        "full_name": "Ali Valiyev",
        "role": "patient"
      },
      "type": "text",
      "content": "Salom, doktor!",
      "created_at": "2026-01-06T10:25:00Z",
      "is_read_by_recipient": true,
      "attachments": []
    }
  ]
}
```

### 2.4 Xabarlarni O'qilgan Deb Belgilash

```http
POST /api/conversations/{id}/mark_as_read/
Authorization: Bearer {token}
```

---

## 🔌 3. WebSocket - Real-time Chat

### 3.1 Ulanish

```javascript
// WebSocket URL formati
const conversationId = 1;
const token = "eyJ0eXAiOiJKV1QiLCJhbGci...";
const wsUrl = `wss://admin.medmapp.uz/ws/chat/${conversationId}/?token=${token}`;

const socket = new WebSocket(wsUrl);

socket.onopen = () => {
  console.log("✅ WebSocket ulandi!");
};

socket.onclose = (event) => {
  console.log(`❌ WebSocket yopildi: ${event.code}`);
  // Qayta ulanish logikasini qo'shing
};

socket.onerror = (error) => {
  console.error("WebSocket xatosi:", error);
};
```

### 3.2 Xabar Yuborish

```javascript
// Xabar yuborish formati
socket.send(JSON.stringify({
  message: "Salom, doktor!",
  type: "text"  // optional, default: "text"
}));
```

### 3.3 Xabar Qabul Qilish

```javascript
socket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case "chat_message":
      // Yangi xabar keldi
      console.log("Yangi xabar:", data.data);
      /*
        data.data = {
          id: 102,
          sender: { id: 2, full_name: "Dr. Komil" },
          content: "Salom! Nima bilan yordam bera olaman?",
          type: "text",
          created_at: "2026-01-06T10:30:00Z",
          is_read_by_recipient: false
        }
      */
      break;
      
    case "status_update":
      // Suhbat statusi o'zgardi
      console.log("Status yangilandi:", data.data);
      break;
      
    case "error":
      // Xatolik
      console.error("Xato:", data.error, data.code);
      break;
  }
};
```

### 3.4 Close Kodlari

| Kod | Nomi | Sabab |
|-----|------|-------|
| 4001 | Unauthorized | Token yo'q yoki noto'g'ri |
| 4003 | Forbidden | Suhbatga ruxsat yo'q |
| 4000 | Bad Request | Noto'g'ri URL format |
| 4500 | Internal Error | Server xatosi |

### 3.5 Rate Limiting

> ⚠️ **Limit:** 5 xabar/sekund

Agar limit oshsa, quyidagi xabar keladi:

```json
{
  "error": "Juda ko'p so'rov. 1 soniya kuting.",
  "code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 1
}
```

---

## 📎 4. Fayl Yuborish

### 4.1 Fayl Yuklash (HTTP orqali)

```http
POST /api/conversations/{id}/upload_file/
Authorization: Bearer {token}
Content-Type: multipart/form-data

file: [binary]
message: "Mana rasm"  (optional)
```

**Response:**
```json
{
  "message": {
    "id": 103,
    "type": "file",
    "content": "Mana rasm",
    "attachments": [
      {
        "id": 5,
        "file": "https://admin.medmapp.uz/media/chat_attachments/2026/01/06/103_image.jpg",
        "file_type": "image",
        "mime_type": "image/jpeg",
        "size": 102400,
        "original_name": "image.jpg"
      }
    ]
  }
}
```

---

## 🔄 5. Frontend Integratsiya Algoritmi

```
┌────────────────────────────────────────────────────────────┐
│  1. LOGIN: /api/token/ → access_token olish               │
└──────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────┐
│  2. CONVERSATIONS: /api/conversations/ → ro'yxat olish    │
└──────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────┐
│  3. SELECT: Foydalanuvchi suhbat tanlaydi (id=1)          │
└──────────────────────────┬─────────────────────────────────┘
                           │
           ┌───────────────┴───────────────┐
           │                               │
           ▼                               ▼
┌──────────────────────┐     ┌─────────────────────────────┐
│ 4a. HISTORY:         │     │ 4b. WEBSOCKET:              │
│ /api/conversations/  │     │ wss://.../ws/chat/1/        │
│ 1/messages/          │     │ ?token=...                  │
│ (Xabar tarixini      │     │ (Real-time ulanish)         │
│  yuklash)            │     │                             │
└──────────────────────┘     └──────────────┬──────────────┘
                                            │
                                            ▼
                             ┌─────────────────────────────┐
                             │ 5. CHAT: Xabar almashish    │
                             │ - Yuborish: socket.send()   │
                             │ - Qabul: socket.onmessage   │
                             └─────────────────────────────┘
```

---

## 🛡️ 6. Xavfsizlik Eslatmalari

| Xavfsizlik | Tavsif |
|------------|--------|
| ✅ JWT Auth | Barcha so'rovlarda token kerak |
| ✅ XSS Protection | Server tomonida HTML escape qilinadi |
| ✅ Rate Limiting | 5 xabar/sekund limit |
| ✅ Access Control | Faqat suhbat ishtirokchilari |
| ✅ SSL/TLS | Barcha ulanishlar HTTPS/WSS |

---

## 🧪 7. Test Qilish

### WebSocket Test (Browser Console)

```javascript
// Browser console da test qilish
const token = "YOUR_JWT_TOKEN";
const ws = new WebSocket(`wss://admin.medmapp.uz/ws/chat/1/?token=${token}`);

ws.onopen = () => console.log("Connected!");
ws.onmessage = (e) => console.log("Message:", JSON.parse(e.data));
ws.onerror = (e) => console.error("Error:", e);

// Xabar yuborish
ws.send(JSON.stringify({ message: "Test xabar" }));
```

---

## ❓ Tez-tez So'raladigan Savollar

**Q: WebSocket uzilsa nima qilish kerak?**
A: Qayta ulanish logikasini qo'shing. Eslatma: yangi token olish shart emas agar access token hali amal qilsa.

**Q: Fayl yuborishda WebSocket ishlatsa bo'ladimi?**
A: Yo'q. Fayllar faqat HTTP (`/upload_file/`) orqali yuklanadi. Keyin WebSocket orqali boshqa ishtirokchiga xabar keladi.

**Q: Conversation ID ni qayerdan olaman?**
A: `GET /api/conversations/` so'rovidan yoki yangi suhbat yaratganda.

---

**Muallif:** Medmapp Backend Team  
**Aloqa:** support@medmapp.uz
