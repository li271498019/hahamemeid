#!/bin/bash
# End-to-end test for haha-agent-chat (frozen spec v1.0).
# Usage: BASE_URL=http://127.0.0.1:8899 CHANNEL_API_KEY=<key> bash test-e2e.sh
# Uses the spec's example agent (agentId 30) and its owner aiId as test data.
# Cleans up the test question/history rows at the end (the agent_memory row
# for agent 30 is left in place: it is the correct default-persona state).
set -u
BASE="${BASE_URL:-http://127.0.0.1:8899}"
KEY="${CHANNEL_API_KEY:-}"
AGENT_ID=30
AI_ID="0x17367f0410c1e90ee380b4a47be765a910dbf2be0db717b1da19e1d6f03670ed"
WRONG_AI_ID="0x0000000000000000000000000000000000000000000000000000000000000001"
NAME="test-agent-name-placeholder"
# NOTE: NAME is resolved from the agent itself; the test submits the real
# domain name. It is fetched from the service via the pending response, so
# the test does not hardcode a domain. The submit below uses the domain
# returned by the indexer API for agent 30 (queried first).
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }
check() { # check <desc> <expected-status> <actual-status> [extra]
  if [ "$2" = "$3" ]; then ok "$1 (HTTP $3)"; else fail "$1 (expected HTTP $2, got HTTP $3) $4"; fi
}

[ -n "$KEY" ] || { echo "CHANNEL_API_KEY is not set"; exit 2; }

# Resolve the agent's real domain from the indexer (no hardcoded domain).
DOMAIN=$(ssh -i ~/.ssh/id_ed25519 -o UserKnownHostsFile=~/.ssh/known_hosts root@<SERVER_IP> \
  "sudo -u haha psql -d haha_indexer -t -A -c \"SELECT n.full_name FROM agents a JOIN names n ON n.token_id = a.name_token_id WHERE a.agent_id = 30;\"" 2>/dev/null | tr -d '[:space:]')
[ -n "$DOMAIN" ] || { echo "could not resolve agent 30 domain"; exit 2; }
echo "test agent: id=30 domain=$DOMAIN"

echo "== 1. GET /health =="
CODE=$(curl -s -o /tmp/e2e_health.json -w "%{http_code}" "$BASE/health")
BODY=$(cat /tmp/e2e_health.json)
check "health returns 200 ok:true" 200 "$CODE" "$BODY"
echo "   body: $BODY"

echo "== 2. POST /questions (chat) =="
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/questions" -H "Content-Type: application/json" \
  -d "{\"agentId\": 30, \"name\": \"$DOMAIN\", \"aiId\": \"$AI_ID\", \"lang\": \"zh\", \"message\": \"e2e test question one\"}")
CODE=$(echo "$RESP" | tail -1); BODY=$(echo "$RESP" | head -n -1)
check "submit chat question" 200 "$CODE" "$BODY"
Q1=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('questionId',''))" 2>/dev/null)
echo "   questionId: $Q1"
[ -n "$Q1" ] || { echo "no questionId returned"; exit 2; }

echo "== 3. POST /questions too fast -> 429 =="
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/questions" -H "Content-Type: application/json" \
  -d "{\"agentId\": 30, \"name\": \"$DOMAIN\", \"aiId\": \"$AI_ID\", \"lang\": \"zh\", \"message\": \"too fast\"}")
CODE=$(echo "$RESP" | tail -1); BODY=$(echo "$RESP" | head -n -1)
check "second submit within 5s -> 429" 429 "$CODE" "$BODY"
echo "   body: $BODY"

echo "== 4. GET /questions/pending without Bearer -> 401 =="
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/questions/pending")
check "pending without Bearer -> 401" 401 "$CODE"

echo "== 5. GET /questions/pending with Bearer =="
RESP=$(curl -s -w "\n%{http_code}" "$BASE/questions/pending" -H "Authorization: Bearer $KEY")
CODE=$(echo "$RESP" | tail -1); BODY=$(echo "$RESP" | head -n -1)
check "pending with Bearer" 200 "$CODE" "$BODY"
echo "$BODY" | grep -q "$Q1" && ok "pending contains our questionId" || fail "pending missing our questionId"
echo "$BODY" | grep -q "\"name\": *\"$DOMAIN\"" && ok "pending name is the real domain" || fail "pending name mismatch"
echo "$BODY" | grep -q "我是 haha agent" && ok "pending persona self-identifies as haha agent" || fail "pending persona identity wrong"

echo "== 6. POST /answers with wrong agentId -> 400 agent_mismatch =="
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/answers" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d "{\"questionId\": \"$Q1\", \"agentId\": 31, \"answer\": \"wrong agent\"}")
CODE=$(echo "$RESP" | tail -1); BODY=$(echo "$RESP" | head -n -1)
check "answer with mismatched agentId -> 400" 400 "$CODE" "$BODY"
echo "$BODY" | grep -q "agent_mismatch" && ok "error code is agent_mismatch" || fail "error code is not agent_mismatch: $BODY"

echo "== 7. POST /answers (correct) with a memory update =="
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/answers" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d "{\"questionId\": \"$Q1\", \"agentId\": 30, \"answer\": \"e2e test answer one\", \"memory\": [{\"op\": \"set\", \"key\": \"e2e-test-key\", \"value\": \"e2e-test-value\"}]}")
CODE=$(echo "$RESP" | tail -1); BODY=$(echo "$RESP" | head -n -1)
check "answer question" 200 "$CODE" "$BODY"

echo "== 8. POST /answers again (duplicate) -> 200 duplicate:true =="
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/answers" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d "{\"questionId\": \"$Q1\", \"agentId\": 30, \"answer\": \"duplicate answer\"}")
CODE=$(echo "$RESP" | tail -1); BODY=$(echo "$RESP" | head -n -1)
check "duplicate answer returns 200" 200 "$CODE" "$BODY"
echo "$BODY" | grep -q '"duplicate": *true' && ok "duplicate flag is true" || fail "duplicate flag missing: $BODY"

echo "== 9. GET /questions/{id} -> answered =="
RESP=$(curl -s -w "\n%{http_code}" "$BASE/questions/$Q1")
CODE=$(echo "$RESP" | tail -1); BODY=$(echo "$RESP" | head -n -1)
check "get question status" 200 "$CODE" "$BODY"
echo "$BODY" | grep -q '"status": *"answered"' && ok "status is answered" || fail "status is not answered: $BODY"
echo "$BODY" | grep -q "e2e test answer one" && ok "answer text matches (first answer wins)" || fail "answer text mismatch: $BODY"

echo "== 10. GET /questions/{nonexistent} -> 404 =="
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/questions/q_00000000000000000000000000")
check "nonexistent question -> 404" 404 "$CODE"

echo "== 11. GET /history (wrong aiId) -> 403 =="
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/history/30?aiId=$WRONG_AI_ID&limit=50")
check "history with wrong aiId -> 403" 403 "$CODE"

echo "== 12. GET /history (correct aiId) =="
RESP=$(curl -s -w "\n%{http_code}" "$BASE/history/30?aiId=$AI_ID&limit=50")
CODE=$(echo "$RESP" | tail -1); BODY=$(echo "$RESP" | head -n -1)
check "history with correct aiId" 200 "$CODE" "$BODY"
echo "$BODY" | grep -q "e2e test question one" && ok "history contains our question" || fail "history missing our question"
echo "$BODY" | grep -q "e2e test answer one" && ok "history contains our answer" || fail "history missing our answer"

echo "== 13. save flow: submit type=save, pending carries history =="
sleep 6
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/questions" -H "Content-Type: application/json" \
  -d "{\"agentId\": 30, \"name\": \"$DOMAIN\", \"aiId\": \"$AI_ID\", \"lang\": \"zh\", \"message\": \"保存对话\", \"type\": \"save\"}")
CODE=$(echo "$RESP" | tail -1); BODY=$(echo "$RESP" | head -n -1)
check "submit save instruction" 200 "$CODE" "$BODY"
Q2=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('questionId',''))" 2>/dev/null)
echo "   save questionId: $Q2"
RESP=$(curl -s "$BASE/questions/pending" -H "Authorization: Bearer $KEY")
echo "$RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
qs = [q for q in d.get('questions', []) if q.get('questionId') == '$Q2']
if not qs:
    print('FAIL: save question not in pending'); sys.exit(1)
q = qs[0]
print('PASS: save question in pending, type =', q.get('type'))
h = q.get('history')
if isinstance(h, list) and len(h) > 0:
    print('PASS: save question carries history (%d messages)' % len(h))
else:
    print('FAIL: save question has no history')
"
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/answers" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d "{\"questionId\": \"$Q2\", \"agentId\": 30, \"answer\": \"已保存\", \"memory\": [{\"op\": \"delete\", \"key\": \"e2e-test-key\"}]}")
CODE=$(echo "$RESP" | tail -1); BODY=$(echo "$RESP" | head -n -1)
check "answer save instruction" 200 "$CODE" "$BODY"

echo "== 14. image flow: answer with an image, then fetch it =="
sleep 6
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/questions" -H "Content-Type: application/json" \
  -d "{\"agentId\": 30, \"name\": \"$DOMAIN\", \"aiId\": \"$AI_ID\", \"lang\": \"zh\", \"message\": \"e2e image question\"}")
CODE=$(echo "$RESP" | tail -1); BODY=$(echo "$RESP" | head -n -1)
check "submit image question" 200 "$CODE" "$BODY"
Q3=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('questionId',''))" 2>/dev/null)
IMG_B64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/answers" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d "{\"questionId\": \"$Q3\", \"agentId\": 30, \"answer\": \"e2e image answer\", \"images\": [{\"mime\": \"image/png\", \"data\": \"$IMG_B64\"}]}")
CODE=$(echo "$RESP" | tail -1); BODY=$(echo "$RESP" | head -n -1)
check "answer with image" 200 "$CODE" "$BODY"
RESP=$(curl -s "$BASE/questions/$Q3")
IMG_URL=$(echo "$RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
imgs = d.get('images') or []
print(imgs[0]['url'] if imgs else '')
" 2>/dev/null)
echo "   image URL: $IMG_URL"
[ -n "$IMG_URL" ] && ok "question response carries image URL" || fail "question response has no image URL"
IMG_ID=$(basename "$IMG_URL")
CODE=$(curl -s -o /tmp/e2e_img.png -w "%{http_code}" "$BASE/images/$IMG_ID")
check "fetch image by id" 200 "$CODE"
file /tmp/e2e_img.png | grep -qi "PNG" && ok "fetched file is a PNG" || fail "fetched file is not a PNG"
CTYPE=$(curl -s -I "$BASE/images/$IMG_ID" | grep -i "^content-type:" | tr -d '\r')
echo "   $CTYPE"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/images/AAAAAAAAAAAAAAAAAAAAAA")
check "nonexistent image -> 404" 404 "$CODE"

echo "== 15. POST /questions with bad aiId format -> 403 =="
sleep 6
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/questions" -H "Content-Type: application/json" \
  -d "{\"agentId\": 30, \"name\": \"$DOMAIN\", \"aiId\": \"not-an-aiid\", \"lang\": \"zh\", \"message\": \"bad aiid\"}")
check "bad aiId format -> 403" 403 "$CODE"

echo "== cleanup test rows =="
ssh -i ~/.ssh/id_ed25519 -o UserKnownHostsFile=~/.ssh/known_hosts root@<SERVER_IP> \
  "sudo -u haha psql -d haha_indexer -t -c \"DELETE FROM agent_images WHERE question_id IN ('$Q1','$Q2','$Q3'); DELETE FROM agent_chat_history WHERE question_id IN ('$Q1','$Q2','$Q3'); DELETE FROM agent_questions WHERE question_id IN ('$Q1','$Q2','$Q3');\"" 2>&1 | tr '\n' ' '; echo
echo "   (image files under /var/www/haha.meme/agent-images/ for this test are left; the 3-day cleanup removes them. Test image id: $IMG_ID)"
echo
echo "RESULT: PASS=$PASS FAIL=$FAIL"
[ "$FAIL" = 0 ]
