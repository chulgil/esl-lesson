"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { BackLink } from "@/components/nav/BackLink";
import { InviteFriends } from "@/components/game/InviteFriends";
import { PlayerBadge } from "@/components/game/PlayerBadge";
import { ReviewPanel } from "@/components/game/ReviewPanel";
import { ShareResultButton } from "@/components/game/ShareResultButton";
import { fetchMe } from "@/lib/api";
import { gameApi, type TypingHistoryItem } from "@/lib/game-api";
import { useInviteTheme } from "@/lib/use-invite-theme";
import {
  GameSocket,
  type GameReviewItem,
  type PlayerProfile,
  type ServerMsg,
  type TpResult,
  type TpStartMsg,
} from "@/lib/game-ws";

type Phase = "lobby" | "waiting" | "countdown" | "racing" | "ended";

interface Row {
  name: string;
  chars: number;
  wpm: number;
  done: boolean;
}

/** 공백 무시 매칭 — 정답 체크에서 스페이스를 건너뛴다 (2026-08-10 사용자 기획).
 *
 * 모바일 키보드의 자동 공백/공백 누락이 오타가 되지 않게, 입력과 목표 문장을
 * 둘 다 공백 제거 후 비교한다. prefix 는 원문(target) 인덱스 기준 — 진행줄
 * 표시와 서버 중계(chars)가 원문 길이를 쓰기 때문에 건너뛴 공백을 포함한다.
 */
function stripSpaces(s: string): string {
  return s.replace(/\s+/g, "");
}

function matchIgnoringSpaces(
  value: string,
  target: string,
): { prefix: number; matched: number; wrong: number } {
  const typed = stripSpaces(value);
  let ti = 0; // 원문 인덱스
  let n = 0; // 공백 제외 정타 수
  while (ti < target.length && n < typed.length) {
    if (/\s/.test(target[ti])) {
      ti += 1;
      continue;
    }
    if (target[ti] !== typed[n]) break;
    ti += 1;
    n += 1;
  }
  // 정타 직후의 공백도 통과 처리 — 진행줄이 단어 경계에서 멈춰 보이지 않게
  while (ti < target.length && /\s/.test(target[ti])) ti += 1;
  return { prefix: ti, matched: n, wrong: typed.length - n };
}

export default function TypingRacePage() {
  return (
    <Suspense>
      <TypingRaceInner />
    </Suspense>
  );
}

/** 영문 타자연습 — 같은 문장을 1~4인이 동시에, 전원 완성 시 다음 문장 (typing-race.md) */
function TypingRaceInner() {
  const joinCode = useSearchParams().get("join");
  const [phase, setPhase] = useState<Phase>("lobby");
  // 초대 입장(?theme=)이면 게임 동안 초대자 테마 — 종료/이탈 시 자동 복원
  useInviteTheme(phase === "ended");
  // 결과가 화면 하단에 묻혀 안 보이는 문제(모바일) — 종료 시 결과 섹션을 상단으로 스크롤
  const resultRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (phase === "ended") {
      resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [phase]);
  const [code, setCode] = useState("");
  const [room, setRoom] = useState<{
    code: string | null;
    host: string;
    players: string[];
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [start, setStart] = useState<TpStartMsg | null>(null);
  const [idx, setIdx] = useState(0);
  const [typed, setTyped] = useState("");
  const [rows, setRows] = useState<Record<string, Row>>({});
  const [myDone, setMyDone] = useState(false);
  const [end, setEnd] = useState<{
    results: TpResult[];
    winner: string | null;
  } | null>(null);
  const [review, setReview] = useState<GameReviewItem[]>([]);
  // 플레이어 배지 (이름 -> 마스코트·칭호) — 대기실·결과에 표시
  const [profiles, setProfiles] = useState<Record<string, PlayerProfile>>({});
  // 지난 기록 리스트 — "지난번의 나"를 이기는 동기 (2026-08-11 요청)
  const [history, setHistory] = useState<TypingHistoryItem[]>([]);
  const [myName, setMyName] = useState("나");
  const socketRef = useRef<GameSocket | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const errorsRef = useRef(0);
  const prevLenRef = useRef(0);
  const lastSentRef = useRef(0);
  const myNameRef = useRef("나");
  // 문장별 남은 시간 — 예고 없이 다음 문장으로 넘어가는 "끊김" 체감 방지
  const [timeLeft, setTimeLeft] = useState(0);
  const deadlineRef = useRef(0);
  const secondsRef = useRef(60);

  useEffect(() => {
    fetchMe().then((me) => {
      if (me) {
        setMyName(me.nickname);
        myNameRef.current = me.nickname;
      }
    });
  }, []);

  useEffect(() => {
    if (phase !== "lobby" && phase !== "ended") return;
    gameApi
      .typingHistory()
      .then((res) => setHistory(res.items))
      .catch(() => undefined);
  }, [phase]);

  const handleMessage = useCallback((msg: ServerMsg) => {
    switch (msg.t) {
      case "tp.room":
        setRoom({ code: msg.code, host: msg.host, players: msg.players });
        if (msg.profiles) setProfiles(msg.profiles);
        setPhase("waiting");
        break;
      case "tp.start": {
        setStart(msg);
        if (msg.profiles) setProfiles(msg.profiles);
        secondsRef.current = msg.sentence_seconds;
        setEnd(null);
        setReview([]);
        setRows(
          Object.fromEntries(
            msg.players.map((name) => [
              name,
              { name, chars: 0, wpm: 0, done: false },
            ]),
          ),
        );
        setPhase("countdown");
        setTimeout(() => setPhase("racing"), msg.countdown * 1000);
        break;
      }
      case "tp.sentence":
        setIdx(msg.idx);
        setTyped("");
        setMyDone(false);
        errorsRef.current = 0;
        prevLenRef.current = 0;
        lastSentRef.current = 0;
        deadlineRef.current = Date.now() + secondsRef.current * 1000;
        setTimeLeft(secondsRef.current);
        setRows((prev) =>
          Object.fromEntries(
            Object.values(prev).map((r) => [
              r.name,
              { ...r, chars: 0, done: false },
            ]),
          ),
        );
        break;
      case "tp.typing":
        setRows((prev) => ({
          ...prev,
          [msg.name]: {
            name: msg.name,
            chars: msg.chars,
            wpm: msg.wpm,
            done: prev[msg.name]?.done ?? false,
          },
        }));
        break;
      case "tp.done_mark":
        setRows((prev) => ({
          ...prev,
          [msg.name]: {
            name: msg.name,
            chars: prev[msg.name]?.chars ?? 0,
            wpm: msg.wpm,
            done: true,
          },
        }));
        break;
      case "tp.review":
        setReview(msg.items);
        break;
      case "tp.end":
        setEnd({ results: msg.results, winner: msg.winner });
        setPhase("ended");
        break;
      case "error":
        setPhase("lobby");
        setError(
          {
            sentences_insufficient:
              "타자연습에 쓸 문장이 부족해요 — 콘텐츠를 등록하면 문장이 쌓여요.",
            room_not_found: "방을 찾을 수 없어요.",
            room_full: "방이 가득 찼어요 (최대 4명).",
          }[msg.code] ?? msg.code,
        );
        break;
    }
  }, []);

  useEffect(() => {
    const socket = new GameSocket(handleMessage, () => {
      setError((prev) => prev ?? "연결이 끊어졌어요. 새로고침해주세요.");
    });
    socket.connect();
    socketRef.current = socket;
    // 초대 링크(?join=)로 진입 시 자동 입장
    const timer = joinCode
      ? setTimeout(() => socket.tpJoin(joinCode), 400)
      : null;
    return () => {
      if (timer) clearTimeout(timer);
      socket.close();
    };
  }, [handleMessage, joinCode]);

  useEffect(() => {
    if (phase === "racing") inputRef.current?.focus();
  }, [phase, idx]);

  // 문장별 카운트다운 표시 (받아쓰기/스크램블과 동일 패턴)
  useEffect(() => {
    if (phase !== "racing") return;
    const t = setInterval(() => {
      setTimeLeft(
        Math.max(0, Math.ceil((deadlineRef.current - Date.now()) / 1000)),
      );
    }, 250);
    return () => clearInterval(t);
  }, [phase]);

  const sentences = start?.sentences ?? [];
  const target = sentences[idx]?.en ?? "";
  const targetKo = sentences[idx]?.ko ?? "";
  // 공백 무시 매칭 — 렌더/전송이 같은 결과를 쓰도록 한 번만 계산
  const typedMatch = matchIgnoringSpaces(typed, target);

  function onType(value: string) {
    if (phase !== "racing" || myDone) return;
    const info = matchIgnoringSpaces(value, target);
    const typedLen = stripSpaces(value).length;
    // 오타 카운트 — 공백 입력은 무시, 새 글자가 매치를 늘리지 못하면 오타
    if (typedLen > prevLenRef.current && info.wrong > 0) {
      errorsRef.current += 1;
    }
    prevLenRef.current = typedLen;

    const prefix = info.prefix;
    // 진행 중계는 2자 이상 변할 때만 — 메시지 폭주 방지
    if (Math.abs(prefix - lastSentRef.current) >= 2) {
      lastSentRef.current = prefix;
      socketRef.current?.tpTyping(idx, prefix);
    }
    setRows((prev) => ({
      ...prev,
      [myNameRef.current]: {
        name: myNameRef.current,
        chars: prefix,
        wpm: prev[myNameRef.current]?.wpm ?? 0,
        done: false,
      },
    }));

    if (info.matched === stripSpaces(target).length) {
      socketRef.current?.tpDone(idx, target.length, errorsRef.current);
      setMyDone(true);
      setTyped("");
      setRows((prev) => ({
        ...prev,
        [myNameRef.current]: {
          ...(prev[myNameRef.current] ?? {
            name: myNameRef.current,
            wpm: 0,
          }),
          name: myNameRef.current,
          chars: target.length,
          done: true,
        },
      }));
      return;
    }
    setTyped(value);
  }

  const playerRows = Object.values(rows);

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-4 py-8 sm:px-10">
      <header className="mb-6 flex items-center gap-4">
        {(phase === "lobby" || phase === "ended") && (
          <BackLink href="/game" label="게임" />
        )}
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">영문 타자연습</span>
        </h1>
        {phase === "racing" && start && (
          <span className="ml-auto flex items-center gap-2">
            <span
              className={`rounded-full px-3 py-1 text-sm font-bold shadow-sm ${
                timeLeft <= 10 ? "bg-brick-red/15 text-brick-red" : "bg-white"
              }`}
            >
              {timeLeft}초
            </span>
            <span className="rounded-full bg-white px-3 py-1 text-sm font-bold shadow-sm">
              {idx + 1} / {start.total}
            </span>
          </span>
        )}
      </header>

      {error && <p className="mb-4 text-sm text-brick-red">{error}</p>}

      {phase === "lobby" && (
        <section className="flex max-w-lg flex-col gap-6">
          <div className="rounded-lg border-2 border-ink/10 bg-white p-4 text-sm">
            <p className="mb-2 font-bold">게임 방식</p>
            <ul className="flex flex-col gap-1 opacity-80">
              <li>
                샘플 문장 하나가 나오면 <b>모두가 같은 문장</b>을 타이핑해요
                (1~4명)
              </li>
              <li>
                <b>전원이 완성하면 다음 문장</b>으로 — 총 10문장, 문장당 최대
                1분
              </li>
              <li>
                <b>띄어쓰기(공백)는 안 쳐도 돼요</b> — 정답 체크에서 무시돼요
              </li>
              <li>
                플레이어마다 진행 줄과 <b>WPM(타속)</b>이 실시간으로 표시돼요
              </li>
              <li>승부: 완성 문장 → 정타 수 → 빠르기 순으로 가려요</li>
            </ul>
          </div>

          {history.length > 0 && (
            <div className="rounded-lg border-2 border-ink/10 bg-white p-4">
              <p className="mb-2 text-sm font-bold">
                내 기록
                <span className="ml-2 text-xs font-normal opacity-60">
                  최근 {history.length}판 — 지난번의 나를 이겨보세요
                </span>
              </p>
              <ul className="flex flex-col gap-1 text-sm">
                {history.map((h, i) => (
                  <li
                    key={`${h.played_at}-${i}`}
                    className="flex flex-wrap items-center gap-x-2 border-b border-ink/5 py-1 last:border-b-0"
                  >
                    <span className="text-xs opacity-50">
                      {h.played_at
                        ? `${new Date(h.played_at).getMonth() + 1}/${new Date(h.played_at).getDate()}`
                        : "-"}
                    </span>
                    <span className="font-bold">평균 {h.cpm}타</span>
                    <span className="opacity-70">최고 {h.peak_cpm}타</span>
                    <span className="text-xs opacity-60">
                      정확도 {Math.round(h.accuracy * 100)}%
                    </span>
                    <span className="ml-auto text-xs">
                      {h.mode === "solo" ? (
                        <span className="opacity-50">혼자</span>
                      ) : h.outcome === "win" ? (
                        <span className="font-bold text-brick-green">승리</span>
                      ) : h.outcome === "lose" ? (
                        <span className="text-brick-red">패배</span>
                      ) : (
                        <span className="opacity-50">무승부</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="rounded-lg border-2 border-ink/10 bg-white p-4">
            <p className="mb-3 text-sm font-bold">혼자 연습 (기록 도전)</p>
            <Brick
              color="green"
              onClick={() => {
                setError(null);
                socketRef.current?.tpSolo();
              }}
            >
              타자 연습 시작
            </Brick>
          </div>

          <div className="rounded-lg border-2 border-ink/10 bg-white p-4">
            <p className="mb-3 text-sm font-bold">친구와 레이스 (2~4인)</p>
            <div className="flex flex-wrap items-center gap-3">
              <Brick
                color="blue"
                onClick={() => {
                  setError(null);
                  socketRef.current?.tpCreate();
                }}
              >
                방 만들기
              </Brick>
              <div className="flex items-center gap-2">
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                  placeholder="방 코드"
                  maxLength={6}
                  className="min-h-11 w-28 rounded-md border-2 border-ink/20 px-2 font-mono uppercase transition-colors focus:border-brick-blue focus:outline-none"
                />
                <Brick
                  color="yellow"
                  onClick={() => {
                    if (!code.trim()) return;
                    setError(null);
                    socketRef.current?.tpJoin(code.trim());
                  }}
                >
                  입장
                </Brick>
              </div>
            </div>
          </div>
        </section>
      )}

      {phase === "waiting" && room && (
        <section className="flex max-w-lg flex-col items-start gap-4 rounded-lg border-2 border-ink/10 bg-white p-5">
          <p>
            친구에게 방 코드를 알려주세요:{" "}
            <span className="rounded bg-highlight/60 px-3 py-1 font-mono text-2xl font-bold tracking-widest">
              {room.code}
            </span>
          </p>
          <div className="flex flex-wrap gap-2">
            {room.players.map((p) => (
              <span
                key={p}
                className="rounded-full border-2 border-brick-blue/40 bg-white px-3 py-1.5 text-sm font-bold"
              >
                <PlayerBadge
                  name={p}
                  profile={profiles[p]}
                  suffix={p === room.host ? " (방장)" : undefined}
                />
              </span>
            ))}
            {Array.from({ length: 4 - room.players.length }, (_, i) => (
              <span
                key={`empty-${i}`}
                className="rounded-full border-2 border-dashed border-ink/15 px-3 py-1.5 text-sm opacity-40"
              >
                빈 자리
              </span>
            ))}
          </div>
          <div className="flex gap-3">
            {room.host === myName && (
              <Brick
                color="green"
                disabled={room.players.length < 2}
                onClick={() => socketRef.current?.tpBegin()}
              >
                시작하기 ({room.players.length}/4)
              </Brick>
            )}
            <Brick
              color="yellow"
              onClick={() => {
                socketRef.current?.tpLeave();
                setPhase("lobby");
              }}
            >
              나가기
            </Brick>
          </div>
          {room.host !== myName && (
            <p className="text-xs opacity-60">방장이 시작하면 바로 달려요!</p>
          )}
          <InviteFriends
            onInvite={(uid) =>
              room.code && socketRef.current?.invite(uid, "typing", room.code)
            }
          />
        </section>
      )}

      {phase === "countdown" && (
        <p className="animate-pulse font-hand text-6xl font-bold text-brick-green">
          준비...
        </p>
      )}

      {phase === "racing" && (
        <section className="flex max-w-2xl flex-col gap-4">
          {/* 샘플 문장 — 모두가 같은 문장을 침 */}
          <div className="rounded-lg border-2 border-ink/10 bg-white p-5 font-mono text-lg leading-relaxed">
            {target.split("").map((ch, i) => {
              // 공백 무시 매칭 — 정타는 원문 prefix, 오타는 그 뒤로 오타 수만큼
              const wrongEnd = Math.min(
                target.length,
                typedMatch.prefix + typedMatch.wrong,
              );
              const state = myDone
                ? "correct"
                : i < typedMatch.prefix
                  ? "correct"
                  : i < wrongEnd
                    ? "wrong"
                    : i === wrongEnd
                      ? "cursor"
                      : "rest";
              return (
                <span
                  key={`${idx}-${i}`}
                  className={
                    state === "correct"
                      ? "text-brick-green"
                      : state === "wrong"
                        ? "bg-brick-red/20 text-brick-red"
                        : state === "cursor"
                          ? "border-b-4 border-brick-blue"
                          : "opacity-60"
                  }
                >
                  {ch}
                </span>
              );
            })}
          </div>

          {targetKo && (
            <p className="rounded-md bg-highlight/40 px-3 py-1.5 text-sm">
              뜻: <b>{targetKo}</b>
            </p>
          )}

          <input
            ref={inputRef}
            value={typed}
            onChange={(e) => onType(e.target.value)}
            disabled={myDone}
            autoComplete="off"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            placeholder={
              myDone ? "완료! 다른 플레이어를 기다리는 중..." : "여기에 타이핑"
            }
            className="w-full rounded-lg border-2 border-ink/30 bg-white px-4 py-3 font-mono text-lg focus:border-brick-blue focus:outline-none disabled:opacity-60"
          />

          {/* 플레이어별 실시간 진행 줄 + 개별 WPM */}
          <div className="flex flex-col gap-2">
            {playerRows.map((row) => {
              const ratio = target.length
                ? Math.min(1, row.chars / target.length)
                : 0;
              const mine = row.name === myName;
              return (
                <div
                  key={row.name}
                  className={`rounded-md border-2 p-2.5 ${
                    mine
                      ? "border-brick-blue/50 bg-white"
                      : "border-ink/10 bg-white"
                  }`}
                >
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="font-bold">
                      {row.name}
                      {mine && " (나)"}
                      {row.done && (
                        <span className="ml-1.5 text-brick-green">완성!</span>
                      )}
                    </span>
                    <span className="rounded bg-ink/5 px-1.5 py-0.5 font-mono font-bold">
                      {Math.round(row.wpm * 5)}타
                      <span className="ml-1 font-normal opacity-60">
                        {Math.round(row.wpm)}WPM
                      </span>
                    </span>
                  </div>
                  <div className="font-mono text-sm leading-snug">
                    <span
                      className={
                        row.done ? "text-brick-green" : "text-brick-blue"
                      }
                    >
                      {target.slice(0, row.chars)}
                    </span>
                    <span className="opacity-30">
                      {target.slice(row.chars)}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-ink/10">
                    <div
                      className={`h-full rounded-full transition-[width] duration-200 ${
                        row.done ? "bg-brick-green" : "bg-brick-yellow"
                      }`}
                      style={{ width: `${ratio * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {phase === "ended" && end && (
        <section
          ref={resultRef}
          className="flex max-w-md flex-col gap-4 rounded-lg border-2 border-ink/10 bg-white p-6"
        >
          <h2 className="font-hand text-3xl font-bold">
            {end.winner ? (
              <span className="hl">{end.winner} 승리!</span>
            ) : end.results.length > 1 ? (
              "무승부"
            ) : (
              "기록 완료!"
            )}
          </h2>
          {end.results.map((r) => (
            <div
              key={r.name}
              className={`rounded-md border-2 p-3 ${
                end.winner === r.name
                  ? "border-brick-yellow bg-highlight/40"
                  : "border-ink/10"
              }`}
            >
              <p className="font-bold">
                <PlayerBadge name={r.name} profile={profiles[r.name]} />
              </p>
              <p className="mt-1 text-sm opacity-80">
                평균 <b>{r.cpm}타</b> · 최고 <b>{r.peak_cpm}타</b> · {r.wpm}
                WPM
              </p>
              <p className="mt-0.5 text-xs opacity-60">
                정확도 {Math.round(r.accuracy * 100)}% · {r.sentences}문장 (
                {r.chars}자)
              </p>
            </div>
          ))}
          <ReviewPanel
            items={review}
            source="typing"
            heading="복습하면 좋을"
            noun="문장"
            hint="추가한 문장은 학습 큐에 들어가요 — 문장 카드는 학습 레벨 '고급'에서 출제돼요"
          />
          <div className="flex gap-3">
            <Brick
              color="green"
              onClick={() => {
                setError(null);
                socketRef.current?.tpSolo();
              }}
            >
              한 번 더
            </Brick>
            <Brick color="blue" href="/game">
              게임 메뉴로
            </Brick>
            {end.results[0] && (
              <ShareResultButton
                data={{
                  game: "영문 타자연습",
                  headline: end.winner
                    ? `${end.winner} 승리!`
                    : end.results.length > 1
                      ? "무승부"
                      : "기록 완료!",
                  scoreline: `최고 ${
                    (end.winner
                      ? end.results.find((r) => r.name === end.winner)
                      : end.results[0]
                    )?.peak_cpm ?? end.results[0].peak_cpm
                  }타`,
                  tone: end.winner ? "win" : "neutral",
                  lines: end.results.slice(0, 4).map((r) => ({
                    label: r.name,
                    value: `평균 ${r.cpm}타 · 정확도 ${Math.round(r.accuracy * 100)}%`,
                  })),
                }}
              />
            )}
          </div>
        </section>
      )}
    </main>
  );
}
