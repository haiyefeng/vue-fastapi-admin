<p align="center">
  <img alt="Logo" width="200" src="./deploy/sample-picture/logo.svg">
</p>

<h1 align="center">vue-fastapi-admin</h1>

English | [简体中文](./README.md)

A separated front-end/back-end platform built on FastAPI + Vue3 + Naive UI, with RBAC permission management, dynamic routing, and JWT authentication.

On top of that base it adds personal productivity modules: an Eisenhower-matrix todo board, habit tracking, goals and reviews, time blocking, and a companion WeChat mini program.

### Features

- **Stack**: Python 3.11 + FastAPI + Tortoise ORM on the back end; Vue3 + Vite + Naive UI on the front end, with pnpm for package management
- **Dynamic routing**: menus are served by the back end and combined with the RBAC model for menu-level control
- **Fine-grained permissions**: button- and endpoint-level control — the front-end `v-permission` directive mirrors the back-end `DependPermission` check
- **JWT auth**: JSON Web Tokens for authentication and authorization
- **Migrations in version control**: `migrations/` is tracked in git and is the single source of truth for the schema; a test catches any drift between models and migrations

### Screenshots

| | |
|---|---|
| Login | ![Login](./deploy/sample-picture/login.jpg) |
| Workbench | ![Workbench](./deploy/sample-picture/workbench.jpg) |
| Users | ![Users](./deploy/sample-picture/user.jpg) |
| Roles | ![Roles](./deploy/sample-picture/role.jpg) |
| Menus | ![Menus](./deploy/sample-picture/menu.jpg) |
| APIs | ![APIs](./deploy/sample-picture/api.jpg) |

### Quick start

> The database is MySQL (only the mysql connection is active in `app/settings/config.py`) and there is
> **no working SQLite fallback**. A bare `docker run` of the app container will not start: `init_db()`
> fails to reach the database and exits, and `--restart=always` just restarts it in a loop. Use the
> docker compose setup below — it brings up a dedicated MySQL container alongside the app.
>
> Full deployment notes (local dev / local container / NAS, which component reads which `.env`
> variable, and troubleshooting) are in [`docs/deployment.md`](docs/deployment.md) (Chinese).

```sh
git clone https://github.com/haiyefeng/vue-fastapi-admin.git
cd vue-fastapi-admin

# Fill in the database password and friends. Leaving WX_APPID / WX_SECRET empty is fine —
# the app still starts, WeChat login just returns 40013.
cp .env.example .env

docker compose up -d --build
```

Open <http://localhost:7777> and sign in with `admin` / `123456`.

```sh
docker compose logs -f app     # application logs (stdout only, nothing written to disk)
docker compose ps              # health status
docker compose down            # stop
docker compose down -v         # stop and wipe the container's database data
```

To deploy somewhere else (a NAS, for example), build and export the image on your dev machine:

```sh
./build-image.sh v1.0.0        # builds and exports vue-fastapi-admin-v1.0.0.tar
```

On the target machine run `docker load -i vue-fastapi-admin-v1.0.0.tar`, then start it with `docker-compose.nas.yml`.

### Local development

You need Python 3.11+, Node, and a local MySQL 8.

#### Back end

Dependencies are declared in `pyproject.toml` + `uv.lock`. Install them with [uv](https://github.com/astral-sh/uv):

```sh
pip install uv                 # skip if already installed
uv sync                        # creates .venv and restores the exact locked versions
source .venv/bin/activate      # Windows: .\.venv\Scripts\activate

cp .env.example .env           # fill in your local MySQL details
python run.py
```

API docs are at <http://localhost:9999/docs>.

The image installs `uv sync --no-dev`, which omits black / isort / ruff / pytest.

#### Front end

```sh
cd web
npm i -g pnpm                  # skip if already installed
pnpm i
pnpm dev
```

Runs on <http://localhost:3100>; in dev mode Vite proxies `/api/v1` to the back end.

#### Common commands

```sh
make test           # run the test suite
make check          # format and lint checks (no changes)
make format         # format
make migrate        # generate a migration after changing models
make upgrade        # apply migrations
```

### Project layout

```
├── app                     // Back end
│   ├── api/v1              // Thin routing layer, one directory per resource:
│   │                       //   apis / auditlog / base / category / dashboard / depts
│   │                       //   goal / habit / menus / pet / project / review
│   │                       //   roles / subtask / timeblock / todos / users
│   ├── controllers         // Business logic, subclassing CRUDBase from core/crud.py
│   ├── core                // Middleware, auth dependencies, generic CRUD, startup init
│   ├── models              // Tortoise ORM models: admin.py / todo.py / pet.py
│   ├── schemas             // Pydantic request/response models
│   ├── settings            // Configuration
│   └── utils               // Helpers (password, JWT, WeChat API, ...)
├── web                     // Front end (Vue3 + Vite)
│   └── src
│       ├── api             // Single entry point for all back-end calls
│       ├── components      // Shared components
│       ├── router          // Routes and guards (dynamic routes derive from back-end menus)
│       ├── store           // Pinia: user / permission / app / tags
│       └── views           // Pages: login / workbench / system / todo / profile
├── weapp                   // WeChat mini program
├── migrations              // Database migrations (tracked in git)
├── tests                   // Back-end tests
├── deploy                  // nginx config and entrypoint used by the Dockerfile, screenshots
└── docs                    // Deployment and design documents
```

### Credits

Forked from [mizhexiaoxiao/vue-fastapi-admin](https://github.com/mizhexiaoxiao/vue-fastapi-admin) — the RBAC and dynamic-routing foundation comes from that project.
