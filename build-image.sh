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

# 保存为tar文件
echo "正在将镜像保存为tar文件..."
docker save vue-fastapi-admin:$VERSION -o vue-fastapi-admin-$VERSION.tar

echo "镜像已保存为 vue-fastapi-admin-$VERSION.tar"