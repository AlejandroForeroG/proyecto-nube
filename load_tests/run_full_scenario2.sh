#!/bin/bash
set -e

# ============================================================================
# Script automatizado para ejecutar TODAS las pruebas del Escenario 2
# Genera CSVs listos para análisis
# ============================================================================

BUCKET="miso-proyecto-nube-2"
S3_FILE_50MB="s3://${BUCKET}/uploads/test_video_50MB.mp4"
S3_FILE_100MB="s3://${BUCKET}/uploads/test_video_100MB.mp4"
RESULTS_DIR="load_tests/results"

echo "========================================================================"
echo "  ESCENARIO 2 - Worker Throughput Tests (Automated)"
echo "========================================================================"
echo ""
echo "Bucket: $BUCKET"
echo "Results: $RESULTS_DIR"
echo ""
echo "Matriz de pruebas:"
echo "  - Tamaños: 50MB, 100MB"
echo "  - Concurrencia: 1, 2, 4"
echo "  - Modos: burst, sustained"
echo ""
echo "Presiona Ctrl+C en los próximos 5s para cancelar..."
sleep 5

# Crear directorio de resultados
mkdir -p "$RESULTS_DIR"

# Función para ejecutar prueba y calcular métricas
run_test() {
    local size=$1
    local concurrency=$2
    local mode=$3
    local count=$4
    local rate=$5
    local s3_file=$6
    
    local label="${size}mb_c${concurrency}_${mode}"
    local csv_output="${RESULTS_DIR}/metrics_${label}.csv"
    echo ""
    echo "========================================================================"
    echo "  TEST: ${label}"
    echo "  Size: ${size}MB | Concurrency: ${concurrency} | Mode: ${mode}"
    echo "  Count: ${count} | Rate: ${rate}/min"
    echo "========================================================================"
    
    # Pausa para ajustar concurrencia manualmente en la instancia del worker
    echo ""
    echo "⚠️  ACCIÓN REQUERIDA: Configurar worker concurrency=${concurrency}"
    echo ""
    echo "Ve a la INSTANCIA DEL WORKER y ejecuta estos comandos:"
    echo ""
    echo "  sed -i -E 's/--concurrency=[0-9]+/--concurrency=${concurrency}/' compose.worker.yml"
    echo "  docker compose -f compose.worker.yml up -d --force-recreate --build"
    echo ""
    echo "Cuando el worker esté listo, presiona ENTER para continuar..."
    read -r
    
    echo "[1/3] Worker configurado. Continuando con la prueba..."
    sleep 5
    
    # Inyectar tareas (SIN monitor para evitar el bug)
    echo "[2/3] Inyectando ${count} tareas (${mode})..."
    if [ "$mode" == "burst" ]; then
        docker compose -f compose.app.yml exec -T rest_api \
            python load_tests/inject_worker_tasks.py \
            --count "$count" \
            --size "${size}MB" \
            --file "$s3_file" \
            --mode burst
    else
        docker compose -f compose.app.yml exec -T rest_api \
            python load_tests/inject_worker_tasks.py \
            --count "$count" \
            --size "${size}MB" \
            --file "$s3_file" \
            --mode sustained \
            --rate "$rate"
    fi
    
    # Esperar confirmación del usuario
    echo ""
    echo "[3/3] Tareas inyectadas. Monitorea el progreso del worker:"
    echo ""
    echo "  En la INSTANCIA DEL WORKER, ejecuta:"
    echo "  docker compose -f compose.worker.yml logs -f celery_worker"
    echo ""
    echo "  Busca mensajes: 'Task ... succeeded' o 'Task ... failed'"
    echo ""
    echo "Cuando todas las tareas hayan terminado (${count} videos), presiona ENTER para calcular métricas..."
    read -r
    
    # Calcular métricas y generar CSV
    echo ""
    echo "Calculando métricas (último .log)..."
    LATEST_LOG=$(docker compose -f compose.app.yml exec -T rest_api sh -lc 'ls -t load_tests/results/worker_tasks_*.log | head -1' | tr -d '\r')
    if [ -z "$LATEST_LOG" ]; then
        echo "No se encontró worker_tasks_*.log dentro de rest_api. Revisa que la inyección generó el log."
        exit 1
    fi
    docker compose -f compose.app.yml exec -T rest_api \
        python load_tests/compute_worker_metrics.py \
        --tasks-log "$LATEST_LOG" \
        --output-csv "/my-app/${csv_output}"
    
    echo "✓ Métricas guardadas en: ${csv_output}"
    echo ""
}

# ============================================================================
# MATRIZ DE PRUEBAS
# ============================================================================

# Concurrencia = 1
run_test 100 1 sustained 20  5  "$S3_FILE_100MB"

# Concurrencia = 2
run_test 50  2 burst     40  0  "$S3_FILE_50MB"
run_test 50  2 sustained 50 20  "$S3_FILE_50MB"
run_test 100 2 burst     20  0  "$S3_FILE_100MB"
run_test 100 2 sustained 30 10  "$S3_FILE_100MB"

# Concurrencia = 4
run_test 50  4 burst     80  0  "$S3_FILE_50MB"
run_test 50  4 sustained 100 30 "$S3_FILE_50MB"
run_test 100 4 burst     40  0  "$S3_FILE_100MB"
run_test 100 4 sustained 60 15  "$S3_FILE_100MB"

# ============================================================================
# CONSOLIDAR RESULTADOS
# ============================================================================

echo ""
echo "========================================================================"
echo "  CONSOLIDANDO RESULTADOS"
echo "========================================================================"

CONSOLIDATED="${RESULTS_DIR}/scenario2_consolidated.csv"

# Crear header del CSV consolidado
echo "size_mb,concurrency,mode,count,throughput_videos_per_min,service_avg_seconds,service_p50_seconds,total,done,failed" > "$CONSOLIDATED"

# Combinar todos los CSVs individuales
for csv in ${RESULTS_DIR}/metrics_*.csv; do
    if [ -f "$csv" ]; then
        # Extraer metadata del nombre del archivo (ej: metrics_50mb_c1_burst.csv)
        filename=$(basename "$csv" .csv)
        size=$(echo "$filename" | grep -oP '\d+(?=mb)')
        conc=$(echo "$filename" | grep -oP '(?<=_c)\d+')
        mode=$(echo "$filename" | grep -oP '(burst|sustained)')
        
        # Agregar al consolidado (skip header)
        tail -n +2 "$csv" | awk -v s="$size" -v c="$conc" -v m="$mode" -F',' \
            '{print s","c","m","$3","$8","$9","$10","$1","$2","$3}' >> "$CONSOLIDATED"
    fi
done

echo "✓ CSV consolidado: ${CONSOLIDATED}"
echo ""
echo "========================================================================"
echo "  PRUEBAS COMPLETADAS"
echo "========================================================================"
echo ""
echo "Resultados en: ${RESULTS_DIR}/"
echo "  - CSVs individuales: metrics_*.csv"
echo "  - CSV consolidado: scenario2_consolidated.csv"
echo ""
echo "Siguiente paso: Analizar los CSVs y documentar en:"
echo "  capacity-planning/escenario_2_worker_throughput.md"
echo ""

