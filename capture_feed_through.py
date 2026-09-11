"""TX1/RX1 feed-through repeatability diagnostic; never writes calibration.

Join the ANTENNA ENDS of the TX1 and RX1 feed cables with an adapter.
Keep both switches and all feed cables in circuit. Antennas 1 are removed
from this path. Run: python capture_feed_through.py
"""
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from time import sleep

ROOT = Path(__file__).resolve().parent


def main():
    import hardware
    import calibration
    from scan_engine import process_sweep_data

    cal_path = ROOT/'2-6_cal_with_new_cable.cal'
    cal_bytes = cal_path.read_bytes()
    cal = calibration.get_calibration(str(cal_path))
    print('Join TX1 and RX1 feed cables at their ANTENNA ends using the adapter.')
    print('Keep VNA -> TX switch -> TX1 feed -> adapter -> RX1 feed -> RX switch -> VNA.')
    print('Do not move connections during capture. No calibration will be overwritten.')
    input('Press Enter once that connection is ready, or Ctrl+C to cancel: ')
    adapter_note = input('Describe adapter/additional cable used (e.g. SMA female-female, no extra cable): ').strip()
    if not adapter_note:
        raise ValueError('Adapter description is required for interpreting the delay.')
    reference_note = input('Where were the VNA calibration standards connected? Type unknown if unsure: ').strip() or 'unknown'
    detected = hardware.auto_detect_devices()
    tx_port, rx_port, config = hardware.resolve_tx_rx_ports(detected['switch_ports'])
    if not detected['vna_port'] or not tx_port or not rx_port:
        raise RuntimeError('VNA and both switch boards must be connected.')
    report = {'timestamp_utc':datetime.now(timezone.utc).isoformat(), 'pair':'TX1-RX1', 'wiring':'VNA port1 -> TX common -> TX1 feed cable -> adapter -> RX1 feed cable -> RX common -> VNA port2', 'adapter_note':adapter_note, 'calibration_reference_note':reference_note, 'calibration_file':cal_path.name, 'calibration_sha256':hashlib.sha256(cal_bytes).hexdigest(), 'start_hz':2000000000, 'stop_hz':6000000000, 'points':101, 'records':[], 'complete':False}
    output = ROOT/'dataset'/('feed_through_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    output.parent.mkdir(exist_ok=True)
    serials = []
    def save():
        output.write_text(json.dumps(report,indent=2,allow_nan=False))
    try:
        for port, role in [(detected['vna_port'],'VNA'),(tx_port,'TX'),(rx_port,'RX')]:
            ser, _, _ = hardware.open_serial_connection_with_fallbacks(port,'Auto',role)
            if not ser:
                raise RuntimeError(f'Could not open {role}')
            serials.append(ser)
        vna, tx, rx = serials
        def select(channel):
            acks = []
            for ser in (tx,rx):
                acks.append(hardware.send_switch_command(ser,hardware.format_switch_command(channel)))
                sleep(0.1)
            return acks
        initial_acks = select(1)
        hardware.set_vna_sweep(vna,2000000000,6000000000,101)
        sleep(0.2)
        for mode in ['fixed_channel','switch_away_and_back']:
            for repeat in range(1,6):
                acks = {'initial':initial_acks}
                if mode == 'switch_away_and_back':
                    acks = {'away':select(2),'back':select(1)}
                hardware.clear_vna_fifo(vna)
                raw = hardware.read_vna_data(vna,101)
                points = hardware.parse_vna_data(raw,101)
                if sorted(p['freq_idx'] for p in points) != list(range(101)):
                    raise ValueError('Incomplete or duplicate frequency indices; repeat the test.')
                points.sort(key=lambda p:p['freq_idx'])
                if any(abs(p['fwd']) == 0 for p in points):
                    raise ValueError('Zero forward reference in capture.')
                record = {'mode':mode,'repeat':repeat,'switch_responses':acks}
                for name, correction in [('raw',None),('calibrated',cal)]:
                    freqs, _, values = process_sweep_data(points,2000000000,6000000000,101,calibration=correction)
                    if any(not math.isfinite(v.real) or not math.isfinite(v.imag) for v in values):
                        raise ValueError('Nonfinite spectrum')
                    record[name] = {'freqs':freqs,'s21_real':[v.real for v in values],'s21_imag':[v.imag for v in values]}
                report['records'].append(record)
                save()
                print(f'{mode}: {repeat}/5 saved')
        report['complete'] = True
        save()
    finally:
        for ser in serials:
            try:
                ser.close()
            except Exception:
                pass
        print(f'Saved diagnostic: {output}')
    print('Finished. Leave the connection in place until the results are reviewed.')


if __name__ == '__main__':
    main()
