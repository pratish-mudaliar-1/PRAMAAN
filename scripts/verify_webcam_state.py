"""scripts/verify_webcam_state.py — Database verification helper for webcam demo."""
import sqlite3
import json

def verify():
    con = sqlite3.connect("backend/pramaan_dev.db")
    cur = con.cursor()
    print("=" * 80)
    print("PRAMAAN WEBCAM PIPELINE DATABASE VERIFICATION")
    print("=" * 80)
    
    print("\n1. [DEVICE TABLE]")
    cur.execute("SELECT id, serial_number, status, last_accepted_seq, last_accepted_hash FROM device WHERE serial_number='DEV-WEBCAM-001'")
    device = cur.fetchone()
    if device:
        print(f"   Device ID:          {device[0]}")
        print(f"   Serial Number:      {device[1]}")
        print(f"   Status:             {device[2]}")
        print(f"   Accepted Sequence:  {device[3]}")
        print(f"   Last Accepted Hash: {device[4]}")
    else:
        print("   DEV-WEBCAM-001 not found!")

    print("\n2. [OBSERVATIONS TABLE]")
    cur.execute("SELECT id, minute_ts, persons_min, persons_p90, persons_max, chain_ok, record_hash, prev_hash FROM observation WHERE device_id=? ORDER BY minute_ts ASC", (device[0],))
    obs_list = cur.fetchall()
    print(f"   Total Observations Ingested: {len(obs_list)}")
    for i, obs in enumerate(obs_list, 1):
        print(f"   Observation #{i}:")
        print(f"     Minute:      {obs[1]}")
        print(f"     Counts:      min={obs[2]}, p90={obs[3]}, max={obs[4]}")
        print(f"     Chain Valid: {bool(obs[5])}")
        print(f"     Record Hash: {obs[6]}")
        print(f"     Prev Hash:   {obs[7]}")

    print("\n3. [SESSION TABLE]")
    with open(".webcam_state/agent_config.json") as f:
        cfg = json.load(f)
    target_sid = cfg["session_id"]
    cur.execute(
        "SELECT id, source_ref, claimed_count, attendance_status, attendance_ratio, last_evaluated_at, scheduled_start, scheduled_end, zone_id FROM session WHERE id=? OR id=?",
        (target_sid, target_sid.replace("-", "")),
    )
    sess = cur.fetchone()
    if sess:
        print(f"   Session ID:        {sess[0]}")
        print(f"   Source Ref:        {sess[1]}")
        print(f"   Claimed Count:     {sess[2]}")
        print(f"   Attendance Status: {sess[3]}")
        print(f"   Attendance Ratio:  {sess[4]}")
        print(f"   Last Evaluated:    {sess[5]}")
        print(f"   Scheduled Start:   {sess[6]}")
        print(f"   Scheduled End:     {sess[7]}")
        print(f"   Zone ID:           {sess[8]}")
    else:
        print(f"   Session {target_sid} not found in database!")

    print("\n4. [FLAGS TABLE]")
    if sess:
        cur.execute("SELECT id, session_id, flag_type, severity, status, rule_name, description FROM flag WHERE session_id=? OR session_id=?", (target_sid, target_sid.replace("-", "")))
        flags = cur.fetchall()
        print(f"   Total Flags Created: {len(flags)}")
        for f in flags:
            print(f"   Flag ID:   {f[0]}")
            print(f"   Type:      {f[2]}")
            print(f"   Severity:  {f[3]}")
            print(f"   Status:    {f[4]}")
            print(f"   Rule:      {f[5]}")
            print(f"   Desc:      {f[6]}")

    else:
        print("   Skipping flags (session not found)")

    print("=" * 80)

if __name__ == "__main__":
    verify()
