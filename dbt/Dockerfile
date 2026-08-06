FROM python:3.11-slim

WORKDIR /usr/app

RUN pip install --no-cache-dir dbt-core==1.8.9 dbt-postgres==1.8.2

COPY profiles ./profiles
COPY project ./project

WORKDIR /usr/app/project

ENTRYPOINT ["dbt"]
CMD ["run"]
