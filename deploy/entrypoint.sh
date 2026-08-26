#!/bin/sh
set -e

# nginx 后台跑，uvicorn 前台阻塞 —— 保持与改动前一致的进程形态，不引入进程管理器
nginx

# 不用 python run.py：它写死了 reload=True，容器里开文件监听没有意义，
# 还会多一个 reloader 进程；叠加启动期的数据库初始化更是本项目已知的事故源。
exec uvicorn app:app --host 0.0.0.0 --port 9999