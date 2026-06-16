#!/bin/bash
# Script de actualización diaria automatizada
# Ejecutar vía cronjob: 0 3 * * * /ruta/al/proyecto/cron_update.sh

echo "=================================================="
echo "Iniciando actualización diaria: $(date)"
echo "=================================================="

# 1. Ingestar nuevos resultados del día (API-Football)
# Usamos el contenedor 'api' existente
echo "[1/2] Descargando resultados del día..."
docker-compose run --rm api python data/ingest_api_football.py --fetch-players

# 2. Re-entrenar los modelos con la nueva ventana de 12 partidos
echo "[2/2] Re-entrenando modelos de IA con nuevos datos..."
docker-compose run --rm api python models/train_pipeline.py

echo "=================================================="
echo "Actualización completada: $(date)"
echo "Los modelos actualizados ya están sirviendo predicciones frescas."
echo "=================================================="
