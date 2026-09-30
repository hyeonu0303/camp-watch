#!/usr/bin/env python3
"""땅끝오토캠핑장 글램핑 2026-10-17 예약가능 감시 → ntfy 푸시 알림"""
import http.cookiejar, json, os, re, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = "2026-10-17"
BASE = "https://autocamp.haenam.go.kr"
CAL_URL = f"{BASE}/glamping/reserve.html?pid=25&date=2026-10&reserve_form=calendar"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128 Safari/537.36"
TOPIC = os.environ["NTFY_TOPIC"]
STATE = os.path.join(DIR, "state.json")
KST = timezone(timedelta(hours=9))
HEARTBEAT_HOURS = [9, 13, 17, 21]  # 정기 상태 알림 (한국시간)


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def notify(title, message, priority=5):
    body = json.dumps({"topic": TOPIC, "title": title, "message": message,
                       "priority": priority, "click": CAL_URL, "tags": ["tent"]}).encode()
    urllib.request.urlopen(urllib.request.Request("https://ntfy.sh/", data=body,
                           headers={"Content-Type": "application/json"}), timeout=20)


def fetch_calendar():
    user, pw = os.environ["CAMP_ID"], os.environ["CAMP_PW"]
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    opener.addheaders = [("User-Agent", UA)]
    opener.open(f"{BASE}/rankup_module/rankup_member/login.html", timeout=20).read()
    data = urllib.parse.urlencode({"mode": "login", "pre_page": "", "kind": "personal",
                                   "login_id": user, "login_pw": pw}, encoding="euc-kr").encode()
    req = urllib.request.Request(f"{BASE}/mypage/proc.ajax.php", data=data,
                                 headers={"X-Requested-With": "XMLHttpRequest"})
    opener.open(req, timeout=20).read()
    return opener.open(CAL_URL, timeout=20).read().decode("euc-kr", "replace")


def current_slot():
    """지금 시각 기준 가장 최근 정기알림 시각 (예: '2026-09-30 13시')"""
    now = datetime.now(KST)
    past = [h for h in HEARTBEAT_HOURS if h <= now.hour]
    if past:
        return f"{now:%Y-%m-%d} {past[-1]}시"
    return f"{now - timedelta(days=1):%Y-%m-%d} {HEARTBEAT_HOURS[-1]}시"


def heartbeat(state, message):
    slot = current_slot()
    if state.get("hb") == slot:
        return
    notify("✅ 캠핑장 감시 정상 작동 중" if not state.get("error") else "⚠️ 캠핑장 감시 오류 지속",
           f"{message}\n확인 시각: {datetime.now(KST):%m/%d %H:%M}", priority=2)
    state["hb"] = slot
    log(f"정기 알림 전송: {slot}")


def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"rooms": [], "error": False}


def main():
    state = load_state()
    try:
        html = fetch_calendar()
        if "date_info1" not in html:
            raise RuntimeError("달력을 불러오지 못함 (로그인 실패 또는 페이지 구조 변경)")
        rooms = re.findall(r'sdate=' + TARGET + r'&[^"]*"[^>]*><span class="ic_room_ok">가능</span>\s*([^<]+)', html)
        rooms = [r.strip() for r in rooms]
    except Exception as e:
        log(f"오류: {e}")
        if not state.get("error"):
            notify("캠핑장 감시 오류", f"확인 중 오류가 발생했어요: {e}", priority=3)
        state["error"] = True
        heartbeat(state, f"오류: {e}")
        json.dump(state, open(STATE, "w"), ensure_ascii=False)
        return 1

    new = [r for r in rooms if r not in state.get("rooms", [])]
    log(f"{TARGET} 가능 객실: {rooms or '없음'}")
    if new:
        notify(f"🏕️ {TARGET} 예약 가능!", f"가능 객실: {', '.join(rooms)}\n눌러서 바로 예약하세요.")
        log(f"알림 전송: {new}")
    state.update(rooms=rooms, error=False)
    heartbeat(state, f"10/17: " + (f"가능 {len(rooms)}개 - {', '.join(rooms)}" if rooms else "아직 전 객실 마감"))
    json.dump(state, open(STATE, "w"), ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
