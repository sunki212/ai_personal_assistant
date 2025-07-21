FROM postgres:17

# Устанавливаем необходимые пакеты
RUN apt-get update && \
    apt-get install -y \
    postgresql-contrib-17 \    
    postgresql-17-pgvector \     
    postgresql-plpython3-17 \    
    python3-dev \                
    libpython3-dev && \
    rm -rf /var/lib/apt/lists/*

# Копируем скрипт инициализации
COPY init.sql /docker-entrypoint-initdb.d/