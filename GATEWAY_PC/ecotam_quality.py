"""Sprint 13: audit ECOTAM's original (non-aggregated) InfluxDB data.

Anomalies represent acquisition/storage evidence, never a diagnosis of sensor
hardware, radio, or trajectory. No modifications to InfluxDB data are made.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import urllib.parse
import urllib.request
from collections import defaultdict
from typing import Any

import ecotam_history as history

# Broad format/sanity bounds, NOT sensor calibration or flight constraints.
# A negative altitude can be perfectly valid relative to a reference level.
BASIC_BOUNDS: dict[str, tuple[float, float]] = {
    'altitude_m': (-10000, 1000000),
    'pressure_pa': (0.001, 2000000),
    'temperature_c': (-150, 300),
    'battery_v': (0, 100),
    'accel_x': (-10000, 10000),
    'accel_y': (-10000, 10000),
    'accel_z': (-10000, 10000),
    'gyro_x': (-100000, 100000),
    'gyro_y': (-100000, 100000),
    'gyro_z': (-100000, 100000),
}
REQUIRED_FIELDS = tuple(BASIC_BOUNDS)
EVENT_PREVIEW_LIMIT = 150
EXPECTED_INTERVAL_S = 1.0  # Current ECOTAM PC simulator cadence.
GAP_THRESHOLD_S = 2.5


def build_quality_flux(bucket: str, start: dt.datetime, stop: dt.datetime) -> str:
    """No aggregateWindow: averaging would mask gaps, missing fields and sequences."""
    if not isinstance(bucket, str) or not bucket.strip() or len(bucket) > 256:
        raise ValueError('Bucket inválido')
    fields = ', '.join(json.dumps(field) for field in (*REQUIRED_FIELDS, 'sequence'))
    return (f'from(bucket: {json.dumps(bucket)})\n'
            f'  |> range(start: {history._flux_time(start)}, stop: {history._flux_time(stop)})\n'
            f'  |> filter(fn: (r) => r._measurement == "{history.MEASUREMENT}")\n'
            f'  |> filter(fn: (r) => contains(value: r._field, set: [{fields}]))\n'
            '  |> keep(columns: ["_time", "_field", "_value", "source", "device", "session_id"])')


def fetch_quality_rows(config: dict[str, str], start: dt.datetime, stop: dt.datetime
                       ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    endpoint = config['url'] + '/api/v2/query?' + urllib.parse.urlencode({'org': config['org']})
    request = urllib.request.Request(endpoint, data=build_quality_flux(config['bucket'], start, stop).encode(),
                                     headers={'Authorization': 'Token ' + config['token'],
                                              'Content-Type': 'application/vnd.flux',
                                              'Accept': 'application/csv'}, method='POST')
    with urllib.request.urlopen(request, timeout=20) as response:
        contents = response.read(history.MAX_BYTES + 1)
        if len(contents) > history.MAX_BYTES:
            raise ValueError('Dados demais para uma auditoria sem agregação. Selecione um período menor.')
    try:
        rows = history.parse_annotated_csv(contents.decode('utf-8-sig'))
    except ValueError as exc:
        if 'Muitos resultados' in str(exc):
            raise ValueError('Dados demais para uma auditoria sem agregação. Selecione um período menor.') from exc
        raise
    # Legacy sessions are inferred; fresh sessions come from InfluxDB session_id tags.
    return history.assign_sessions(rows, 1)


def _get_sequence(row: dict[str, Any]) -> int | None:
    value = row.get('sequence')
    if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 and float(value).is_integer():
        return int(value)
    return None


def analyze_rows(rows: list[dict[str, Any]], sessions: list[dict[str, Any]],
                 now: dt.datetime | None = None) -> dict[str, Any]:
    """Return precise, traceable per-record findings; never fill gaps with fake data."""
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    ordered = sorted(rows, key=lambda r: (r['time'], r.get('session_key', '')))
    state: dict[str, dict[str, Any]] = {}
    per_session: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    kind_counts: dict[str, int] = defaultdict(int)
    missing_fields: dict[str, int] = defaultdict(int)
    problem_rows: set[int] = set()
    lost_by_gap = 0
    lost_by_sequence = 0
    inferred_missing = 0

    def report(kind: str, severity: str, row: dict[str, Any], explanation: str, index: int,
               field: str = '') -> None:
        kind_counts[kind] += 1
        problem_rows.add(index)
        if len(events) < EVENT_PREVIEW_LIMIT:
            events.append({'time': row['time'], 'session_key': row.get('session_key', ''),
                           'kind': kind, 'severity': severity,
                           'field': field, 'detail': explanation})

    for index, row in enumerate(ordered):
        sid = row.get('session_key') or ':'.join((row.get('source', '?'), row.get('device', '?'),
                                                 row.get('session_id', '') or 'sem-sessao'))
        session = per_session.setdefault(sid, {
            'id': sid, 'samples': 0, 'problem_samples': 0, 'missing_est': 0, 'gaps': 0,
            'dup_sequence': 0, 'invalid_fields': 0,
        })
        session['samples'] += 1
        was_problem = False
        for field, (low, high) in BASIC_BOUNDS.items():
            value = row.get(field)
            if not isinstance(value, (float, int)) or not math.isfinite(value):
                report('campo_ausente', 'warning', row, 'Campo não recuperado ou ilegível', index, field)
                missing_fields[field] += 1
                session['invalid_fields'] += 1
                was_problem = True
            elif not low <= value <= high:
                report('faixa_basica', 'warning', row, f'Valor {value:g} fora da faixa de integridade básica', index, field)
                session['invalid_fields'] += 1
                was_problem = True

        seq = _get_sequence(row)
        if seq is None:
            report('sequencia_ausente', 'warning', row, 'Sequência ausente ou não inteira', index, 'sequence')
            was_problem = True
        timestamp = history.parse_time(row['time'])
        previous = state.get(sid)
        if previous:
            delta = (timestamp - previous['time']).total_seconds()
            missing_by_time = 0
            missing_by_seq = 0
            if delta > GAP_THRESHOLD_S:
                missing_by_time = max(1, round(delta / EXPECTED_INTERVAL_S) - 1)
                session['gaps'] += 1
                lost_by_gap += missing_by_time
                report('lacuna_temporal', 'warning', row,
                       f'Intervalo de {delta:.2f}s após a amostra anterior (esperado ~1s)', index)
                was_problem = True
            if seq is not None and previous['seq'] is not None:
                if seq == previous['seq']:
                    session['dup_sequence'] += 1
                    report('sequencia_duplicada', 'warning', row, f'Sequência {seq} repetida', index, 'sequence')
                    was_problem = True
                elif seq < previous['seq']:
                    report('sequencia_retrocesso', 'warning', row,
                           f'Sequência regrediu de {previous["seq"]} para {seq}', index, 'sequence')
                    was_problem = True
                elif seq > previous['seq'] + 1:
                    missing_by_seq = seq - previous['seq'] - 1
                    lost_by_sequence += missing_by_seq
                    report('salto_sequencia', 'warning', row,
                           f'Entre seq={previous["seq"]} e seq={seq}: {missing_by_seq} identificadores ausentes',
                           index, 'sequence')
                    was_problem = True
            # Avoid counting the same lost sample twice when both clocks and sequence agree.
            session['missing_est'] += max(missing_by_time, missing_by_seq)
            inferred_missing += max(missing_by_time, missing_by_seq)
        # Update previous for each session; do not use data across separate sessions.
        state[sid] = {'time': timestamp, 'seq': seq}
        if was_problem:
            session['problem_samples'] += 1

    observed = len(ordered)
    total_expected_estimate = observed + inferred_missing
    score = None if not observed else round(100 * max(0, observed - len(problem_rows)) /
                                              max(total_expected_estimate, 1), 1)
    last = history.parse_time(ordered[-1]['time']) if ordered else None
    age = round(max(0, (now - last).total_seconds()), 1) if last else None
    result_sessions = []
    for info in sessions:
        stats = per_session.get(info['id'], {})
        result_sessions.append({**info, **stats})
    # Events are capped for UI payload size but totals are never truncated.
    return {
        'samples': observed, 'score_pct': score, 'estimated_missing': inferred_missing,
        'gaps': kind_counts['lacuna_temporal'], 'duplicates': kind_counts['sequencia_duplicada'],
        'bad_samples': len(problem_rows), 'last_age_s': age,
        'last_status': ('SEM DADOS' if not ordered else 'RECENTE' if age is not None and age <= 15
                        else 'SEM DADOS RECENTES'),
        'kinds': dict(kind_counts), 'missing_fields': dict(missing_fields),
        'missing_by_clock': lost_by_gap, 'missing_by_sequence': lost_by_sequence,
        'sessions': result_sessions, 'events': events, 'events_total': sum(kind_counts.values()),
        'events_truncated': sum(kind_counts.values()) > len(events),
        'expected_interval_s': EXPECTED_INTERVAL_S,
    }


def quality_result(config: dict[str, str] | None, payload: dict[str, Any]) -> dict[str, Any]:
    if config is None:
        raise ValueError('Conecte o InfluxDB na página Tempo real antes de analisar.')
    start, stop, _ = history.select_range(payload)
    rows, sessions = fetch_quality_rows(config, start, stop)
    findings = analyze_rows(rows, sessions)
    return {'start': history._flux_time(start), 'stop': history._flux_time(stop),
            'raw': True, 'measurement': history.MEASUREMENT,
            'notes': 'Auditoria de amostras brutas, sem médias. Resultados por sessão; lacunas anteriores à primeira amostra não são inferidas.',
            **findings}
