# Лабораторна робота №1 — Розгортання Web-сервісу з автоматизацією

Веб-застосунок `mywebapp` (Task Tracker) із автоматизованим розгортанням на
віртуальній машині під Linux. Архітектура:

```
client → nginx (:80) → uvicorn/FastAPI (127.0.0.1:3000) → PostgreSQL (127.0.0.1:5432)
```

## Варіант індивідуального завдання

Розрахунок виконано за номером залікової книжки `N = 3697`:

| Формула           | Значення | Сенс                                                |
|-------------------|----------|-----------------------------------------------------|
| `V2 = N % 2 + 1`  | **2**    | Конфігурація через файл `/etc/mywebapp/config.yaml`; СУБД — **PostgreSQL** |
| `V3 = N % 3 + 1`  | **2**    | Тематика — **Task Tracker**                         |
| `V5 = N % 5 + 1`  | **3**    | Порт застосунку — **3000**                          |

### Бізнес-логіка (V3 = 2, Task Tracker)

Об'єкт `Task` містить рівно поля, які вимагає умова: `id`, `title`, `status`,
`created_at`. API:

| Метод | URL                  | Опис                                                            |
|-------|----------------------|-----------------------------------------------------------------|
| GET   | `/tasks`             | Список усіх задач (`id`, `title`, `status`, `created_at`)       |
| POST  | `/tasks`             | Створити нову задачу. Тіло: `{"title": "..."}`                  |
| POST  | `/tasks/<id>/done`   | Позначити задачу як виконану                                    |
| GET   | `/`                  | Plain HTML-список бізнес-ендпоінтів (приймає тільки `text/html`)|
| GET   | `/health/alive`      | Завжди `200 OK` (для liveness-проб)                             |
| GET   | `/health/ready`      | `200 OK` якщо БД доступна, інакше `500` із описом проблеми       |

Усі ендпоінти, які повертають бізнес-дані, поважають заголовок `Accept`:

* `application/json` (за замовчуванням) → JSON
* `text/html` → проста HTML-сторінка **без CSS та JS**; списки рендеряться у
  вигляді HTML-таблиць (як вимагає умова).

`/health/*` назовні через nginx **не пропускаються** — вимога умови щодо того,
що nginx віддає лише кореневий ендпоінт і бізнес-ендпоінти.

### Приклади запитів

```bash
# JSON
curl http://<vm-ip>/tasks
curl -X POST http://<vm-ip>/tasks -H 'Content-Type: application/json' \
     -d '{"title": "buy milk"}'
curl -X POST http://<vm-ip>/tasks/1/done

# HTML
curl -H 'Accept: text/html' http://<vm-ip>/
curl -H 'Accept: text/html' http://<vm-ip>/tasks
```

## Розробка

Вимоги: Python 3.10+, локальний PostgreSQL.

```bash
git clone <repo>
cd Lab1DevOps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Конфіг для локального запуску
cat > /tmp/mywebapp.yaml <<'EOF'
database_url: "postgresql+psycopg2://user:password@127.0.0.1:5432/mywebapp_dev"
EOF

# Запуск міграції та сервера
APP_CONFIG_PATH=/tmp/mywebapp.yaml python -m scripts.migration
APP_CONFIG_PATH=/tmp/mywebapp.yaml python -m uvicorn app.main:app \
    --host 127.0.0.1 --port 3000
```

## Розгортання

### Базовий образ ВМ

Використовується офіційний образ
[**Ubuntu Server 22.04 LTS**](https://ubuntu.com/download/server) (підійде також
24.04 LTS). На VirtualBox/VMware/UTM/Proxmox/Hyper-V/Multipass — рівноцінно.

### Вимоги до ресурсів

| Ресурс | Мінімум | Рекомендовано |
|--------|---------|---------------|
| CPU    | 1 vCPU  | 2 vCPU        |
| RAM    | 1 GiB   | 2 GiB         |
| Disk   | 10 GiB  | 20 GiB        |

Особливих налаштувань при встановленні ОС не потрібно: одна розбивка диску за
замовчуванням, OpenSSH-сервер вмикається у Subiquity-інсталяторі.

### Перший вхід

Після встановлення Ubuntu вхід виконується під дефолтним cloud-користувачем
(`ubuntu` або тим, якого ви вказали в інсталяторі) через **SSH** або
**console**. Credentials — ті, що ви задали в інсталяторі.

> Після виконання `deploy.sh` цей дефолтний користувач буде **заблокований**, і
> вхід можливий тільки під `student`/`teacher`/`operator` (пароль за
> замовчуванням `12345678`, ОС вимагатиме його змінити при першому вході).

### Запуск автоматизації

```bash
# На свіжій ВМ під дефолтним користувачем:
git clone <repo-url> Lab1DevOps
cd Lab1DevOps
sudo bash scripts/deploy.sh
```

Скрипт виконує всі вісім пунктів умови:

1. встановлює пакети (`python3`, `postgresql`, `nginx`, …);
2. створює користувачів `student`, `teacher`, `app`, `operator`;
3. створює БД `mywebapp` і роль `app_user` (PostgreSQL слухає лише `localhost`);
4. розкладає конфіги (`/etc/mywebapp/config.yaml`, `/etc/sudoers.d/operator`);
5. встановлює systemd-юніти `mywebapp.service` + `mywebapp.socket`
   (socket activation);
6. запускає сервіс (із міграцією як `ExecStartPre`);
7. налаштовує nginx (`/etc/nginx/sites-enabled/mywebapp`);
8. створює `/home/student/gradebook` з числом `N`;
9. блокує дефолтного cloud-користувача.

## Користувачі та права

| Користувач | Призначення                       | Доступ                                                        |
|------------|-----------------------------------|---------------------------------------------------------------|
| `student`  | Робота з проєктом                 | у групі `sudo`, пароль `12345678`, потрібна зміна на першому вході |
| `teacher`  | Перевірка                         | у групі `sudo`, пароль `12345678`, потрібна зміна на першому вході |
| `app`      | Запуск застосунку (`systemd`)     | системний, без shell, без home; читає `/etc/mywebapp/config.yaml`  |
| `operator` | Керування сервісом                | `sudo` тільки на конкретні команди (див. `config/sudoers-operator`)|

`operator` може виконувати рівно:

```text
sudo systemctl start|stop|restart|status mywebapp.service
sudo systemctl start|stop|restart|status mywebapp.socket
sudo systemctl reload|status nginx
```

## Тестування розгорнутої системи

```bash
# 1. Health probes на самому VM (назовні не пропускаються)
curl -s http://127.0.0.1:3000/health/alive    # → OK
curl -s http://127.0.0.1:3000/health/ready    # → OK

# 2. Через nginx (порт 80) — лише дозволені ендпоінти
curl -s http://127.0.0.1/                     # plain-HTML список ендпоінтів
curl -sH 'Accept: application/json' http://127.0.0.1/tasks
curl -sH 'Accept: text/html'        http://127.0.0.1/tasks   # HTML-таблиця

curl -s -X POST http://127.0.0.1/tasks \
     -H 'Content-Type: application/json' \
     -d '{"title": "lab review"}'
curl -s -X POST http://127.0.0.1/tasks/1/done

# 3. nginx ховає health назовні
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/health/alive   # → 404

# 4. PostgreSQL слухає тільки localhost
sudo ss -ltnp | grep ':5432'                  # 127.0.0.1:5432 only

# 5. Socket activation
systemctl status mywebapp.socket
systemctl status mywebapp.service

# 6. Перевірка обмежень operator
sudo -u operator -i sudo systemctl restart mywebapp     # ✓
sudo -u operator -i sudo systemctl reload  nginx        # ✓
sudo -u operator -i sudo systemctl disable mywebapp     # ✗ (sudo denied)
sudo -u operator -i sudo ls /root                       # ✗
```

## Структура репозиторію

```
.
├── app/
│   ├── database.py        # SQLAlchemy engine (config via /etc/mywebapp/config.yaml)
│   ├── main.py            # FastAPI — endpoints per V3=2 + content negotiation
│   ├── models.py          # Task (id, title, status, created_at)
│   └── schemas.py         # Pydantic схеми
├── scripts/
│   ├── deploy.sh          # Єдина точка входу автоматизації (Ubuntu Server)
│   └── migration.py       # Ідемпотентна міграція БД
├── config/
│   ├── config.yaml.example
│   ├── mywebapp.service   # systemd service з socket activation
│   ├── mywebapp.socket    # systemd socket на 127.0.0.1:3000
│   ├── nginx.conf         # Reverse proxy, тільки дозволені ендпоінти
│   └── sudoers-operator   # Обмежений sudo для operator
├── requirements.txt
└── README.md
```
