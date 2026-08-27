#!/bin/bash

# 设置版本号
VERSION=$1

if [ -z "$VERSION" ]; then
  echo "请提供版本号，例如: ./build-image.sh v1.0.0"
  exit 1
fi

# 构建镜像
echo "正在构建版本 $VERSION 的镜像..."
docker build -t vue-fastapi-admin:$VERSION .

# docker-compose.nas.yml 引用的镜像名是 vue-fastapi-admin-app（不带 tag，即 :latest），
# 这里额外打上这个名字，NAS 上 docker load 之后 nas 编排就能直接用，不必再手工 tag。
docker tag vue-fastapi-admin:$VERSION vue-fastapi-admin-app:latest

# 保存为tar文件（同一个镜像、两个引用，tar 里只存一份层）
echo "正在将镜像保存为tar文件..."
docker save vue-fastapi-admin:$VERSION vue-fastapi-admin-app:latest -o vue-fastapi-admin-$VERSION.tar

echo "镜像已保存为 vue-fastapi-admin-$VERSION.tar"
echo "NAS 部署：把 tar 传到 NAS → docker load -i vue-fastapi-admin-$VERSION.tar"
echo "         → docker compose -f docker-compose.nas.yml up -d"