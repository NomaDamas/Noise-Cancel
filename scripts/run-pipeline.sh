#!/bin/zsh
# noise-cancel pipeline: scrape -> classify -> deliver
# Intended to be run via cron every hour.

source ~/.zshrc

NC=/Users/jeffrey/PycharmProjects/noise-cancel/.venv/bin/noise-cancel
LOG_DIR=/Users/jeffrey/PycharmProjects/noise-cancel/logs
mkdir -p "$LOG_DIR"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOG_DIR/pipeline.log"

$NC scrape  >> "$LOG_DIR/pipeline.log" 2>&1 && \
$NC classify >> "$LOG_DIR/pipeline.log" 2>&1 && \
$NC deliver  >> "$LOG_DIR/pipeline.log" 2>&1

echo "" >> "$LOG_DIR/pipeline.log"
