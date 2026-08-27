FROM node:20-alpine AS web

# 安装必要的构建依赖
RUN apk add --no-cache python3 make g++

WORKDIR /opt/vue-fastapi-admin
COPY /web ./web

# 设置 npm 镜像源
RUN npm config set registry https://registry.npmmirror.com

# 安装依赖
WORKDIR /opt/vue-fastapi-admin/web
RUN npm install

# 构建项目
RUN npm run build


FROM python:3.11-slim-bullseye

WORKDIR /opt/vue-fastapi-admin

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=core-apt \
    --mount=type=cache,target=/var/lib/apt,sharing=locked,id=core-apt \
    sed -i "s@http://.*.debian.org@http://mirrors.ustc.edu.cn@g" /etc/apt/sources.list \
    && rm -f /etc/apt/apt.conf.d/docker-clean \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev bash nginx vim curl procps net-tools default-mysql-client

# 依赖装在 uv sync 这一层，输入只有 pyproject.toml + uv.lock。
# 单独成层是为了缓存：只改应用代码时这一层不会失效。
# --frozen 表示严格按 uv.lock 装、不重新解析；lock 与 pyproject 不一致时直接报错，
# 而不是悄悄装出一套与开发环境不同的依赖。
# --no-dev 把 black / isort / ruff / pytest 挡在镜像外。
RUN pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY pyproject.toml uv.lock ./
RUN UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple uv sync --frozen --no-dev

# 把 venv 放进 PATH，entrypoint 里就能直接 `uvicorn`，不必套一层 `uv run`。
ENV PATH="/opt/vue-fastapi-admin/.venv/bin:$PATH"

# 应用代码放在依赖层之后：改代码不会让上面的 uv sync 层失效
ADD . .
COPY /deploy/entrypoint.sh .

COPY --from=web /opt/vue-fastapi-admin/web/dist /opt/vue-fastapi-admin/web/dist
ADD /deploy/web.conf /etc/nginx/sites-available/web.conf
RUN rm -f /etc/nginx/sites-enabled/default \ 
    && ln -s /etc/nginx/sites-available/web.conf /etc/nginx/sites-enabled/ 

# 确保entrypoint脚本有正确的换行符和权限
RUN sed -i 's/\r$//' entrypoint.sh && \
    chmod +x entrypoint.sh

ENV LANG=zh_CN.UTF-8
EXPOSE 80

ENTRYPOINT [ "bash", "entrypoint.sh" ]