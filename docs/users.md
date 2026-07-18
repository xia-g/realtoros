# Real Estate OS — Тестовые пользователи
# Пароль для всех: password123
# Хеш (SHA256): ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f

## Администратор
| Email | Телефон | Роль |
|-------|---------|------|
| user0@realtor.ru | +79000100000 | **admin** — Иван Иванов |

## Остальные роли
| Email | Телефон | Имя | Роль |
|-------|---------|-----|------|
| user1@realtor.ru | +79000100001 | Александр Петров | **executive** |
| user2@realtor.ru | +79000100002 | Сергей Сидоров | **broker** |
| user3@realtor.ru | +79000100003 | Андрей Кузнецов | **realtor** |
| user4@realtor.ru | +79000100004 | Дмитрий Попов | **lawyer** |
| user5@realtor.ru | +79000100005 | Максим Смирнов | **compliance** |

## Эндпоинт авторизации
```
POST http://127.0.0.1:8090/api/v1/auth/login
Content-Type: application/json

{"email": "user0@realtor.ru", "password": "password123"}
```
