FROM node:20-alpine AS web

WORKDIR /opt/iandsec-uc
COPY /web ./web
RUN cd /opt/iandsec-uc/web \
    && corepack enable \
    && corepack prepare pnpm@9.15.9 --activate \
    && pnpm config set registry https://registry.npmmirror.com \
    && pnpm install --frozen-lockfile \
    && pnpm run build


FROM python:3.11-slim-bookworm

WORKDIR /opt/iandsec-uc
ENV TZ=Asia/Shanghai
COPY requirements.txt run.py ./
COPY app ./app
COPY deploy/entrypoint.sh .

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=core-apt \
    --mount=type=cache,target=/var/lib/apt,sharing=locked,id=core-apt \
    set -eux; \
    for source_file in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
        if [ -f "$source_file" ]; then \
            sed -i \
                -e "s@http://deb.debian.org/debian-security@http://mirrors.ustc.edu.cn/debian-security@g" \
                -e "s@http://security.debian.org/debian-security@http://mirrors.ustc.edu.cn/debian-security@g" \
                -e "s@http://deb.debian.org/debian@http://mirrors.ustc.edu.cn/debian@g" \
                "$source_file"; \
        fi; \
    done \
    && rm -f /etc/apt/apt.conf.d/docker-clean \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev bash nginx curl default-mysql-client redis-tools fonts-dejavu-core tzdata docker.io \
    && rm -rf /var/lib/apt/lists/*

RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY --from=web /opt/iandsec-uc/web/dist /opt/iandsec-uc/web/dist
ADD /deploy/web.conf /etc/nginx/sites-available/web.conf
RUN rm -f /etc/nginx/sites-enabled/default \
    && ln -s /etc/nginx/sites-available/web.conf /etc/nginx/sites-enabled/ \
    && useradd --system --create-home --home-dir /home/app app \
    && mkdir -p /opt/iandsec-uc/storage /opt/iandsec-uc/app/logs /var/cache/nginx /var/log/nginx /var/lib/nginx \
    && touch /tmp/nginx.pid \
    && chown -R app:app /opt/iandsec-uc /var/cache/nginx /var/log/nginx /var/lib/nginx /tmp/nginx.pid

ENV LANG=zh_CN.UTF-8
EXPOSE 8080

ENTRYPOINT [ "sh", "entrypoint.sh" ]
