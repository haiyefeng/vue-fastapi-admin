<p align="center">
  <a href="https://github.com/mizhexiaoxiao/vue-fastapi-admin">
    <img alt="Vue FastAPI Admin Logo" width="200" src="https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/logo.svg">
  </a>
</p>

<h1 align="center">vue-fastapi-admin</h1>

English | [简体中文](./README.md)

vue-fastapi-admin is a modern front-end and back-end separation development platform that combines FastAPI, Vue3, and Naive UI. It incorporates RBAC (Role-Based Access Control) management, dynamic routing, and JWT (JSON Web Token) authentication, making it ideal for rapid development of small to medium-sized applications and also serves as a valuable learning resource.

### Features
- **Popular Tech Stack**: The backend is developed with the high-performance asynchronous framework FastAPI using Python 3.11, while the front-end is powered by cutting-edge technologies such as Vue3 and Vite, complemented by the efficient package manager, pnpm.
- **Code Standards**: The project is equipped with various plugins for code standardization and quality control, ensuring consistency and enhancing team collaboration efficiency.
- **Dynamic Routing**: Backend dynamic routing combined with the RBAC model allows for fine-grained control of menus and routing.
- **JWT Authentication**: User identity verification and authorization are handled through JWT, enhancing the application's security.
- **Granular Permission Control**: Implements detailed permission management including button and interface level controls, ensuring different roles and users have appropriate permissions.

### Live Demo
- URL: http://139.9.100.77:9999
- Username: admin
- Password: 123456

### Screenshots

#### Login Page
![Login Page](https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/login.jpg)

#### Workbench
![Workbench](https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/workbench.jpg)

#### User Management
![User Management](https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/user.jpg)

#### Role Management
![Role Management](https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/role.jpg)

#### Menu Management
![Menu Management](https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/menu.jpg)

#### API Management
![API Management](https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/api.jpg)

### Quick Start
Please follow the instructions below for installation and configuration:

> **Note**: this project runs on MySQL (the mysql connection is the only live one in
> `app/settings/config.py`); there is no working SQLite fallback any more. A bare
> `docker run` of the app image will **not** work — `init_db()` fails when it cannot reach
> a database, and `--restart=always` just restarts it in a loop. Use docker compose below,
> which brings up a dedicated MySQL container alongside the app.

#### Method 1 (recommended): docker compose

```sh
git clone https://github.com/mizhexiaoxiao/vue-fastapi-admin.git
cd vue-fastapi-admin

# Fill in the database password and friends. WX_APPID / WX_SECRET may stay empty —
# the app still starts, WeChat login just returns 40013.
cp .env.example .env

docker compose up -d --build
```

##### Access the Service

http://localhost:7777

username：admin

password：123456

##### Everyday commands

```sh
docker compose logs -f app     # application logs (stdout only, nothing on disk)
docker compose down            # stop
docker compose down -v         # stop and wipe the container's database data
```

#### Method 2: Build the image only (for NAS or other external hosts)

```sh
./build-image.sh v1.0.0        # builds and exports vue-fastapi-admin-v1.0.0.tar
```

Copy the tar to the target host, `docker load -i vue-fastapi-admin-v1.0.0.tar`, then start it
with `docker-compose.nas.yml` (or your own orchestration). The app container needs a reachable
MySQL, pointed at through the `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME`
environment variables.

username：admin

password：123456

### Local Setup
#### Backend
The backend service requires the following environment:
- Python 3.11

#### Method 1 (Recommended): Install Dependencies with uv
1. Install uv
```sh
pip install uv
```

2. Create and activate virtual environment
```sh
uv venv
source .venv/bin/activate  # Linux/Mac
# or
.\.venv\Scripts\activate  # Windows
```

3. Install dependencies
```sh
uv sync
```

4. Start the backend service
```sh
python run.py
```

#### Method 2: Install Dependencies with Pip
1. Create a Python virtual environment:
```sh
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

2. Install project dependencies:

Dependencies are declared in `pyproject.toml` + `uv.lock`. Install them with
[uv](https://github.com/astral-sh/uv):
```sh
uv sync
```
`uv sync` restores the exact locked versions and creates `.venv` for you, so the
manual venv step above can be skipped. The image installs `uv sync --no-dev`,
which omits black / isort / ruff / pytest.

3. Start the backend service:
```sh
python run.py
```
The backend service is now running, and you can visit http://localhost:9999/docs to view the API documentation.

#### Frontend
The frontend project requires a Node.js environment (recommended version 18.8.0 or higher).
- node v18.8.0+

1. Navigate to the frontend project directory:
```sh
cd web
```

2. Install project dependencies (pnpm is recommended: https://pnpm.io/zh/installation)
```sh
npm i -g pnpm # If pnpm is already installed, skip this step
pnpm i # Or use npm i
```

3. Start the frontend development server:
```sh
pnpm dev
```

### Directory Structure Explanation

```
├── app                   // Application directory
│   ├── api               // API interface directory
│   │   └── v1            // Version 1 of the API interfaces
│   │       ├── apis      // API-related interfaces
│   │       ├── base      // Base information interfaces
│   │       ├── menus     // Menu related interfaces
│   │       ├── roles     // Role related interfaces
│   │       └── users     // User related interfaces
│   ├── controllers       // Controllers directory
│   ├── core              // Core functionality module
│   ├── log               // Log directory
│   ├── models            // Data models directory
│   ├── schemas           // Data schema/structure definitions
│   ├── settings          // Configuration settings directory
│   └── utils             // Utilities directory
├── deploy                // Deployment related directory
│   └── sample-picture    // Sample picture directory
└── web                   // Front-end web directory
    ├── build             // Build scripts and configuration directory
    │   ├── config        // Build configurations
    │   ├── plugin        // Build plugins
    │   └── script        // Build scripts
    ├── public            // Public resources directory
    │   └── resource      // Public resource files
    ├── settings          // Front-end project settings
    └── src               // Source code directory
        ├── api           // API interface definitions
        ├── assets        // Static resources directory
        │   ├── images    // Image resources
        │   ├── js        // JavaScript files
        │   └── svg       // SVG vector files
        ├── components    // Components directory
        │   ├── common    // Common components
        │   ├── icon      // Icon components
        │   ├── page      // Page components
        │   ├── query-bar // Query bar components
        │   └── table     // Table components
        ├── composables   // Composable functionalities
        ├── directives    // Directives directory
        ├── layout        // Layout directory
        │   └── components // Layout components
        ├── router        // Routing directory
        │   ├── guard     // Route guards
        │   └── routes    // Route definitions
        ├── store         // State management (pinia)
        │   └── modules   // State modules
        ├── styles        // Style files directory
        ├── utils         // Utilities directory
        │   ├── auth      // Authentication related utilities
        │   ├── common    // Common utilities
        │   ├── http      // Encapsulated axios
        │   └── storage   // Encapsulated localStorage and sessionStorage
        └── views         // Views/Pages directory
            ├── error-page // Error pages
            ├── login      // Login page
            ├── profile    // Profile page
            ├── system     // System management page
            └── workbench  // Workbench page
```

### Visitors Count

<img align="left" src = "https://profile-counter.glitch.me/vue-fastapi-admin/count.svg" alt="Loading">