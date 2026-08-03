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
ADD . .
COPY /deploy/entrypoint.sh .

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=core-apt \
    --mount=type=cache,target=/var/lib/apt,sharing=locked,id=core-apt \
    sed -i "s@http://.*.debian.org@http://mirrors.ustc.edu.cn@g" /etc/apt/sources.list \
    && rm -f /etc/apt/apt.conf.d/docker-clean \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev bash nginx vim curl procps net-tools default-mysql-client

RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

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