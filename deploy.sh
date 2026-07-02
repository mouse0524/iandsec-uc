#!/bin/sh
set -e

cd "$(dirname "$0")"

git pull

test -f web/dist.zip
rm -rf web/.dist-tmp
mkdir -p web/.dist-tmp
unzip -q web/dist.zip -d web/.dist-tmp
rm -rf web/dist
mv web/.dist-tmp web/dist

docker compose up -d --force-recreate app
