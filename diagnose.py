"""
Diagnostic test: figure out WHY your downloads are failing.

Runs 4 tests on a small sample of videos and tells you what's broken:
  Test 1: Direct connection (your home IP) - is YouTube rate-limiting you?
  Test 2: A few random proxies - are your proxies dead or banned?
  Test 3: Availability check only (no download) - is the bottleneck check or fetch?
  Test 4: Known-good public video - rules out per-video issues.

Run from venv:
    python diagnose.py
"""
import os
import sys
import time
import random
import socket

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig

# Known-good public video with transcripts (TED talk, always available)
CANARY_VIDEO = "arj7oStGLkU"  # TED: Inside the mind of a master procrastinator

# Videos to test - edit this list with IDs from your failed run
TEST_VIDEOS = [
    CANARY_VIDEO,
    "YPD7ZtQQZd0",  # Dr. Ben Bikman (from your failed list)
    "uhi2eNpgz70",  # Reviewing Raw Primal (from your failed list)
]

PROXY_FILE = os.path.join(SCRIPT_DIR, "proxies.txt")


def color(s, c):
    codes = {"g": "\033[92m", "r": "\033[91m", "y": "\033[93m", "b": "\033[94m", "reset": "\033[0m"}
    return f"{codes.get(c,'')}{s}{codes['reset']}"


def try_direct(video_id, timeout=30):
    socket.setdefaulttimeout(timeout)
    try:
        api = YouTubeTranscriptApi()
        tlist = api.list(video_id)
        t = tlist.find_transcript(["en"])
        data = t.fetch()
        return True, f"OK ({len(data)} segments)"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        socket.setdefaulttimeout(None)


def try_proxy(video_id, proxy, timeout=30):
    socket.setdefaulttimeout(timeout)
    try:
        proxy_url = f"http://{proxy}"
        cfg = GenericProxyConfig(http_url=proxy_url, https_url=proxy_url)
        api = YouTubeTranscriptApi(proxy_config=cfg)
        tlist = api.list(video_id)
        t = tlist.find_transcript(["en"])
        data = t.fetch()
        return True, f"OK ({len(data)} segments)"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:100]}"
    finally:
        socket.setdefaulttimeout(None)


def try_list_only_direct(video_id, timeout=20):
    """Availability check only - no transcript download."""
    socket.setdefaulttimeout(timeout)
    try:
        api = YouTubeTranscriptApi()
        tlist = api.list(video_id)
        langs = [t.language_code for t in tlist]
        return True, f"Available: {langs}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        socket.setdefaulttimeout(None)


def load_proxies(n=5):
    if not os.path.exists(PROXY_FILE):
        return []
    with open(PROXY_FILE) as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    return random.sample(lines, min(n, len(lines)))


def main():
    print(color("\n=== YT TRANSCRIPT DIAGNOSTIC ===\n", "b"))

    # TEST 1: canary video, direct
    print(color("[Test 1] Canary video over DIRECT connection (your home IP)", "b"))
    print(f"  Video: https://youtube.com/watch?v={CANARY_VIDEO}")
    ok, msg = try_direct(CANARY_VIDEO)
    print(f"  {color('PASS','g') if ok else color('FAIL','r')}: {msg}\n")
    canary_direct_ok = ok

    # TEST 2: availability-only check (lighter call)
    print(color("[Test 2] Availability check only (no transcript fetch)", "b"))
    ok2, msg2 = try_list_only_direct(CANARY_VIDEO)
    print(f"  {color('PASS','g') if ok2 else color('FAIL','r')}: {msg2}\n")

    # TEST 3: multiple direct calls in rapid succession (triggers rate-limit?)
    print(color("[Test 3] 5 rapid direct calls - detects rate-limiting", "b"))
    successes = 0
    for i in range(5):
        ok3, msg3 = try_direct(CANARY_VIDEO, timeout=15)
        tag = color("OK", "g") if ok3 else color("FAIL", "r")
        print(f"  Attempt {i+1}: {tag} {msg3[:80]}")
        if ok3:
            successes += 1
        time.sleep(1)
    print(f"  Result: {successes}/5 succeeded\n")

    # TEST 4: 5 random proxies
    print(color("[Test 4] 5 random proxies from proxies.txt", "b"))
    proxies = load_proxies(5)
    if not proxies:
        print(color("  No proxies.txt found - skipping\n", "y"))
    else:
        proxy_ok = 0
        for p in proxies:
            ok4, msg4 = try_proxy(CANARY_VIDEO, p, timeout=20)
            tag = color("OK", "g") if ok4 else color("FAIL", "r")
            print(f"  {p[:25]:<25} {tag} {msg4[:80]}")
            if ok4:
                proxy_ok += 1
        print(f"  Result: {proxy_ok}/{len(proxies)} proxies worked\n")

    # TEST 5: the actual videos from your failed list
    print(color("[Test 5] Your previously-failed videos (direct)", "b"))
    for vid in TEST_VIDEOS[1:]:
        ok5, msg5 = try_direct(vid, timeout=20)
        tag = color("OK", "g") if ok5 else color("FAIL", "r")
        print(f"  {vid}: {tag} {msg5[:100]}")
        time.sleep(2)

    # Diagnosis
    print(color("\n=== DIAGNOSIS ===", "b"))
    if not canary_direct_ok:
        print(color("Your home IP CANNOT reach YouTube transcripts at all.", "r"))
        print("  Likely: YouTube has rate-limited/blocked your IP, OR antivirus (ESET) is blocking.")
        print("  Fix: check ESET Web Access Protection, or wait 1-2 hours, or use a VPN.")
    elif canary_direct_ok and successes < 3:
        print(color("Direct works but rate-limits quickly.", "y"))
        print("  Fix: slower delays in direct fallback (raise base_delay to 30s+).")
    elif canary_direct_ok and successes >= 3:
        print(color("Your home IP + YouTube connection is FINE.", "g"))
        print("  The issue is your proxies (dead/banned), not your setup.")
        print("  Fix: get paid proxies (Webshare) or run direct-only.")


if __name__ == "__main__":
    main()
