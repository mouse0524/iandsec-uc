ARG WEB_BASE_IMAGE=iandsec-uc-web-base:latest
ARG APP_BASE_IMAGE=iandsec-uc-app-base:latest
FROM ${WEB_BASE_IMAGE} AS web

WORKDIR /opt/iandsec-uc
COPY /web ./web
RUN cd /opt/iandsec-uc/web \
    && if [ ! -f .web-deps.sha256 ] || ! sha256sum -c .web-deps.sha256; then \
        pnpm install --frozen-lockfile \
        && sha256sum package.json pnpm-lock.yaml > .web-deps.sha256; \
    fi \
    && pnpm run build


FROM ${APP_BASE_IMAGE}

WORKDIR /opt/iandsec-uc
ENV TZ=Asia/Shanghai
COPY requirements.txt pyproject.toml run.py ./
COPY deploy/entrypoint.sh .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked,id=core-pip \
    if [ ! -f .requirements.sha256 ] || ! sha256sum -c .requirements.sha256; then \
        pip install --disable-pip-version-check -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple \
        && pip install --disable-pip-version-check --no-deps chinese-days==0.0.2 -i https://pypi.tuna.tsinghua.edu.cn/simple \
        && sha256sum requirements.txt > .requirements.sha256; \
    fi

COPY app ./app
COPY migrations ./migrations

COPY --from=web /opt/iandsec-uc/web/dist /opt/iandsec-uc/web/dist
ADD /deploy/web.conf /etc/nginx/sites-available/web.conf
ADD /deploy/security-headers.conf /etc/nginx/snippets/security-headers.conf
RUN rm -f /etc/nginx/sites-enabled/default \
    && ln -s /etc/nginx/sites-available/web.conf /etc/nginx/sites-enabled/ \
    && useradd --system --create-home --home-dir /home/app app \
    && mkdir -p /opt/iandsec-uc/storage /opt/iandsec-uc/app/logs /var/cache/nginx /var/log/nginx /var/lib/nginx \
    && touch /tmp/nginx.pid \
    && chown -R app:app /opt/iandsec-uc /var/cache/nginx /var/log/nginx /var/lib/nginx /tmp/nginx.pid

ENV LANG=zh_CN.UTF-8
ENV TRUST_PROXY_HEADERS=1
EXPOSE 8080

ENTRYPOINT [ "sh", "entrypoint.sh" ]
