"""History reader for ECOTAM InfluxDB OSS 2.x (Flux annotated CSV).

This module neither executes arbitrary user Flux nor exposes API credentials.
Analysis uses numeric measurements only, avoiding mean() on boolean fields.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from typing import Any

MEASUREMENT = 'ecotam_telemetry'
NUMERIC_FIELDS = (
    'altitude_m', 'pressure_pa', 'temperature_c', 'battery_v',
    'accel_x', 'accel_y', 'accel_z', 'gyro_x', 'gyro_y', 'gyro_z', 'sequence',
    'humidity_pct', 'latitude', 'longitude', 'gps_altitude_m', 'satellites',
)
PERIODS = {'15m': 900, '1h': 3600, '6h': 21600, '24h': 86400, '7d': 604800, '30d': 2592000}
MAX_DAYS = 31
MAX_BYTES = 12_000_000
MAX_ROWS = 18_000


def parse_time(value: str) -> dt.datetime:
    try:
        out = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('Data inválida. Use um intervalo válido.') from exc
    if out.tzinfo is None:
        raise ValueError('O horário precisa incluir o fuso horário.')
    return out.astimezone(dt.timezone.utc)


def select_range(payload: dict[str, Any], now: dt.datetime | None = None) -> tuple[dt.datetime, dt.datetime, int]:
    now = now or dt.datetime.now(dt.timezone.utc)
    period = str(payload.get('period', '1h'))
    if period == 'custom':
        start = parse_time(str(payload.get('start', '')))
        stop = parse_time(str(payload.get('stop', '')))
    elif period in PERIODS:
        stop = now
        start = stop - dt.timedelta(seconds=PERIODS[period])
    else:
        raise ValueError('Período não permitido.')
    seconds = (stop - start).total_seconds()
    if not (0 < seconds <= MAX_DAYS * 86400):
        raise ValueError('Selecione um intervalo maior que zero e de no máximo 31 dias.')
    if start > now + dt.timedelta(minutes=1):
        raise ValueError('O período começa no futuro.')
    # Approximately 1,800 points per series maximum; always a valid Flux duration.
    every = max(1, math.ceil(seconds / 1800))
    return start, stop, every


def _flux_time(value: dt.datetime) -> str:
    return value.isoformat(timespec='seconds').replace('+00:00', 'Z')


def build_flux(bucket: str, start: dt.datetime, stop: dt.datetime, every: int) -> str:
    if not isinstance(bucket, str) or not bucket.strip() or len(bucket) > 256:
        raise ValueError('Bucket inválido')
    if not 1 <= every <= 86400:
        raise ValueError('Resolução de consulta inválida')
    field_list = ', '.join(json.dumps(name) for name in NUMERIC_FIELDS)
    return (f'from(bucket: {json.dumps(bucket)})\n'
            f'  |> range(start: {_flux_time(start)}, stop: {_flux_time(stop)})\n'
            f'  |> filter(fn: (r) => r._measurement == "{MEASUREMENT}")\n'
            f'  |> filter(fn: (r) => contains(value: r._field, set: [{field_list}]))\n'
            f'  |> aggregateWindow(every: {every}s, fn: mean, createEmpty: false)\n'
            '  |> keep(columns: ["_time", "_field", "_value", "source", "device", "session_id"])')


def parse_annotated_csv(content: str) -> list[dict[str, Any]]:
    """Collapse InfluxDB's per-field tables into per-timestamp sample records."""
    reader = csv.reader(io.StringIO(content))
    columns: list[str] = []
    by_record: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for parts in reader:
        if not parts or parts[0].startswith('#'):
            continue
        if '_time' in parts and '_field' in parts and '_value' in parts:
            columns = parts
            continue
        if not columns:
            continue
        record = dict(zip(columns, parts))
        field = record.get('_field', '')
        if field not in NUMERIC_FIELDS:
            continue
        raw_t = record.get('_time', '')
        raw_v = record.get('_value', '')
        try:
            timestamp = parse_time(raw_t)
            value = float(raw_v)
        except (ValueError, OverflowError):
            continue
        if not math.isfinite(value):
            continue
        # Collapse fractional seconds to ms only; preserve stable event ordering.
        time_iso = timestamp.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        source = record.get('source', '') or 'sem_fonte'
        device = record.get('device', '') or 'sem_dispositivo'
        sid = record.get('session_id', '')
        key = (time_iso, source, device, sid)
        if key not in by_record:
            by_record[key] = {'time': time_iso, 'source': source, 'device': device,
                              'session_id': sid}
            if len(by_record) > MAX_ROWS:
                raise ValueError('Muitos resultados. Escolha um intervalo menor.')
        by_record[key][field] = round(value, 6)
    return sorted(by_record.values(), key=lambda row: (row['time'], row['source'], row['device']))


def assign_sessions(rows: list[dict[str, Any]], resolution_s: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """New data use persisted session_id; legacy data use approximate gap/reset detection."""
    tracks: dict[tuple[str, str], dict[str, Any]] = {}
    sessions: dict[str, dict[str, Any]] = {}
    gap_s = max(90, resolution_s * 3.5)
    for row in rows:
        source, device = row['source'], row['device']
        raw_sid = row.get('session_id', '')
        timepoint = parse_time(row['time'])
        if raw_sid:
            sid = 'tag:' + source + ':' + device + ':' + raw_sid
            approx = False
        else:
            key = (source, device)
            state = tracks.get(key)
            has_gap = not state or (timepoint - state['last_time']).total_seconds() > gap_s
            seq = row.get('sequence')
            sequence_reset = (state is not None and seq is not None and state['last_seq'] is not None
                              and seq + 1 < state['last_seq'])
            if has_gap or sequence_reset:
                count = (state['part'] + 1) if state else 1
                state = {'part': count, 'last_time': timepoint, 'last_seq': seq}
                tracks[key] = state
            else:
                state['last_time'] = timepoint
                if seq is not None:
                    state['last_seq'] = seq
            sid = f'legacy:{source}:{device}:{state["part"]}'
            approx = True
        row['session_key'] = sid
        if sid not in sessions:
            sessions[sid] = {
                'id': sid, 'source': source, 'device': device, 'start': row['time'],
                'end': row['time'], 'points': 0, 'approximate': approx,
            }
        entry = sessions[sid]
        entry['end'] = row['time']
        entry['points'] += 1
    result = sorted(sessions.values(), key=lambda entry: entry['start'], reverse=True)
    return rows, result


def influx_history(config: dict[str, str], start: dt.datetime, stop: dt.datetime, every: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    url = config['url'] + '/api/v2/query?' + urllib.parse.urlencode({'org': config['org']})
    query = build_flux(config['bucket'], start, stop, every)
    request = urllib.request.Request(url, data=query.encode('utf-8'), headers={
        'Authorization': 'Token ' + config['token'],
        'Content-Type': 'application/vnd.flux',
        'Accept': 'application/csv',
    }, method='POST')
    with urllib.request.urlopen(request, timeout=20) as resp:
        # Bounded even if the server reports no Content-Length.
        content = resp.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise ValueError('Consulta muito grande. Escolha um período menor.')
    parsed = parse_annotated_csv(content.decode('utf-8-sig'))
    return assign_sessions(parsed, every)


def history_result(config: dict[str, str] | None, payload: dict[str, Any]) -> dict[str, Any]:
    if config is None:
        raise ValueError('Conecte ao InfluxDB na página principal primeiro.')
    start, stop, every = select_range(payload)
    rows, sessions = influx_history(config, start, stop, every)
    return {'start': _flux_time(start), 'stop': _flux_time(stop), 'resolution_s': every,
            'downsampled': every > 1, 'rows': rows, 'sessions': sessions,
            'fields': list(NUMERIC_FIELDS), 'measurement': MEASUREMENT}
