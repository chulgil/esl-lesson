/** 워드 테트리스 WS 클라이언트 (docs/specs/word-tetris.md 프로토콜) */

import { getAppTheme } from "@/lib/theme";

export interface BrickState {
  id: number;
  display: string;
  y: number;
  landed: boolean;
  garbage: boolean;
  item?: boolean;
  chip?: string | null;
}

export interface BoardState {
  bricks: BrickState[];
  chips: string[];
  direction: "en2ko" | "ko2en";
  input_mode: "tap" | "type";
  combo: number;
  score: number;
  speed_level: number;
  danger: boolean;
  frozen: boolean;
  shield: number;
  items: string[];
  ko: boolean;
}

export interface StateMsg {
  t: "state";
  elapsed: number;
  me: BoardState;
  op: BoardState;
  events: { me: string[]; op: string[] };
}

export interface MatchFoundMsg {
  t: "match.found";
  match_id: number;
  mode: string;
  quiz: string;
  you: number;
  opponent: string;
  countdown: number;
  rejoined?: boolean;
}

export interface ClearResultMsg {
  t: "clear.result";
  seq: number;
  ok: boolean;
  brick_id: number | null;
  combo: number;
  effects: string[];
  score_gained: number;
}

export interface MatchEndMsg {
  t: "match.end";
  winner: "win" | "lose" | "draw";
  stats: {
    p1: MatchPlayerStats;
    p2: MatchPlayerStats;
    duration: number;
  };
  aborted: boolean;
  /** 이번 매치로 경신한 개인 기록 (score/max_combo/wpm — P3) */
  records?: string[];
}

export interface MatchPlayerStats {
  score: number;
  cleared: number;
  misses: number;
  max_combo: number;
  wpm: number;
  accuracy: number;
}

/** 스피드 퀴즈 로얄 (docs/proposal/quiz-royale.md) */
export interface QrRoomMsg {
  t: "qr.room";
  code: string | null;
  mode: "solo" | "room";
  host: string;
  players: { name: string; is_bot: boolean }[];
}

export interface QrRoundMsg {
  t: "qr.round";
  no: number;
  total: number;
  prompt: string;
  choices: string[];
  seconds: number;
}

export interface QrRevealMsg {
  t: "qr.reveal";
  no: number;
  answer: string;
  gains: Record<string, number>;
  scores: QrRank[];
}

export interface QrRank {
  user_id: number | null;
  name: string;
  score: number;
  rank: number;
  is_bot: boolean;
}

export interface QrEndMsg {
  t: "qr.end";
  ranking: QrRank[];
  aborted: boolean;
}

/** 오답·미제출 문항의 학습 항목 — 본인에게만 전달 (원탭 학습 추가, 전 게임 공용) */
export interface GameReviewItem {
  item_id: number;
  en: string;
  ko: string;
}

export type QrMsg =
  | QrRoomMsg
  | QrRoundMsg
  | QrRevealMsg
  | QrEndMsg
  | { t: "qr.review"; items: GameReviewItem[] }
  | { t: "qr.answered"; name: string };

/** 영문 타자연습 — 문장 동기 레이스 1~4인 (docs/specs/typing-race.md) */
export interface TpSentence {
  item_id: number;
  en: string;
  ko: string;
}

export interface TpStartMsg {
  t: "tp.start";
  sentences: TpSentence[];
  total: number;
  sentence_seconds: number;
  countdown: number;
  players: string[];
}

export interface TpResult {
  name: string;
  chars: number;
  sentences: number;
  wpm: number;
  /** 평균 타 (타/분) */
  cpm: number;
  /** 최고 타 (타/분) */
  peak_cpm: number;
  accuracy: number;
}

export type TpMsg =
  | TpStartMsg
  | { t: "tp.room"; code: string | null; host: string; players: string[] }
  | { t: "tp.sentence"; idx: number }
  | { t: "tp.typing"; name: string; chars: number; wpm: number }
  | { t: "tp.done_mark"; name: string; idx: number; wpm: number }
  | { t: "tp.review"; items: GameReviewItem[] }
  | {
      t: "tp.end";
      results: TpResult[];
      winner: string | null;
      aborted: boolean;
    };

/** 어순 조립 레이스 (docs/specs/scramble-race.md) */
export interface ScRound {
  answer: string[];
  chips: string[];
  ko: string;
  item_id: number;
  en: string;
}

export interface ScStartMsg {
  t: "sc.start";
  rounds: ScRound[];
  total: number;
  sentence_seconds: number;
  countdown: number;
  players: string[];
}

export interface ScResult {
  name: string;
  sentences: number;
  mistakes: number;
  score: number;
}

export type ScMsg =
  | ScStartMsg
  | { t: "sc.room"; code: string | null; host: string; players: string[] }
  | { t: "sc.sentence"; idx: number }
  | { t: "sc.progress"; name: string; placed: number; total: number }
  | {
      t: "sc.done_mark";
      name: string;
      idx: number;
      gained: number;
      score: number;
    }
  | { t: "sc.review"; items: GameReviewItem[] }
  | {
      t: "sc.end";
      results: ScResult[];
      winner: string | null;
      aborted: boolean;
    };

/** 받아쓰기 배틀 (docs/specs/dictation-battle.md) */
export interface DtClip {
  video_id: string;
  start_ms: number;
  end_ms: number;
}

export interface DtResult {
  name: string;
  sentences: number;
  accuracy: number;
  score: number;
}

export type DtMsg =
  | {
      t: "dt.start";
      clips: DtClip[];
      total: number;
      sentence_seconds: number;
      countdown: number;
      players: string[];
    }
  | { t: "dt.room"; code: string | null; host: string; players: string[] }
  | { t: "dt.sentence"; idx: number }
  | {
      t: "dt.done_mark";
      name: string;
      idx: number;
      accuracy: number;
      gained: number;
      score: number;
    }
  | { t: "dt.reveal"; idx: number; en: string }
  | { t: "dt.review"; items: GameReviewItem[] }
  | {
      t: "dt.end";
      results: DtResult[];
      winner: string | null;
      aborted: boolean;
    };

/** 학습 관전 — 승인제 릴레이 (docs/specs/study-spectate.md) */
export interface StEventPayload {
  phase: string;
  /** 호스트의 앱 테마 — 관전 화면을 호스트 테마로 렌더 (2026-07-30, theme-mall.md) */
  theme?: string;
  index?: number;
  total?: number;
  correct_count?: number;
  answered_count?: number;
  prompt?: string;
  prompt_ko?: string;
  template?: string;
  choices?: string[];
  result?: { correct: boolean; correct_answer: string };
}

export type StMsg =
  | { t: "st.hosting"; code: string }
  | { t: "st.request"; watcher_id: number; name: string }
  | { t: "st.requested"; host: string }
  | { t: "st.approved"; host: string }
  | { t: "st.denied" }
  | { t: "st.event"; payload: StEventPayload }
  | { t: "st.left"; name: string }
  | { t: "st.chat"; name: string; text: string }
  | { t: "st.cheer"; name: string; kind: string }
  | { t: "st.end" };

/** 친구 게임 초대 (P2) */
export type IvMsg =
  | {
      t: "iv.invited";
      from: string;
      game: "tetris" | "quiz" | "typing" | "scramble" | "dictation";
      code: string;
      /** 초대자 테마 — 게스트 게임 화면에 적용, 종료 시 복원 (무효 값은 서버가 null) */
      theme?: string | null;
    }
  | { t: "iv.sent"; ok: boolean; via?: "ws" | "push" | null };

// --- 채팅·프레즌스 (docs/specs/chat.md) ---
export type ChatServerMsg =
  | {
      t: "chat.message";
      id: number;
      conversation_id: number;
      sender_id: number;
      from_name: string;
      body: string;
      item_ref: {
        item_id: number;
        item_type: string;
        en_text: string;
        ko_text: string;
      } | null;
      image_url: string | null;
      client_msg_id: string;
      created_at: string | null;
    }
  | {
      t: "chat.read";
      conversation_id: number;
      user_id: number;
      last_read_message_id: number;
    }
  | { t: "chat.typing"; from_user_id: number }
  | { t: "presence"; user_id: number; online: boolean };

/** 알림 센터 — payload 는 타입별로 달라 인덱스 시그니처로 수용 (docs/specs/notifications.md) */
export type NotifServerMsg = {
  t: "notif.new";
  type: string;
  [key: string]: unknown;
};

export type ServerMsg =
  | IvMsg
  | ChatServerMsg
  | NotifServerMsg
  | StateMsg
  | MatchFoundMsg
  | ClearResultMsg
  | MatchEndMsg
  | QrMsg
  | TpMsg
  | ScMsg
  | DtMsg
  | StMsg
  | { t: "queue.waiting" }
  | { t: "room.created"; code: string }
  | { t: "attack.recv"; count: number }
  | { t: "item.gained"; item: string }
  | {
      t: "item.result";
      ok: boolean;
      item?: string;
      hint_answer?: string | null;
      cleared?: number;
    }
  | { t: "error"; code: string }
  | { t: "pong" };

export class GameSocket {
  private ws: WebSocket | null = null;
  private seq = 0;

  constructor(
    private onMessage: (msg: ServerMsg) => void,
    private onClose: () => void,
  ) {}

  connect(): void {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${proto}://${window.location.host}/ws/game`);
    this.ws.onmessage = (event) => {
      try {
        this.onMessage(JSON.parse(event.data) as ServerMsg);
      } catch {
        // 파싱 불가 메시지 무시
      }
    };
    this.ws.onclose = () => this.onClose();
  }

  private send(msg: object): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  joinPve(quiz: string, botLevel: number, contentIds?: number[]): void {
    this.send({
      t: "queue.join",
      mode: "pve",
      quiz,
      bot_level: botLevel,
      content_ids: contentIds,
    });
  }
  joinPvp(quiz: string): void {
    this.send({ t: "queue.join", mode: "pvp", quiz });
  }
  leaveQueue(): void {
    this.send({ t: "queue.leave" });
  }
  sendChatTyping(toUserId: number): void {
    this.send({ t: "chat.typing", to: toUserId });
  }
  createRoom(quiz: string, contentIds?: number[]): void {
    this.send({ t: "room.create", quiz, content_ids: contentIds });
  }
  joinRoom(code: string): void {
    this.send({ t: "room.join", code });
  }
  submit(text: string): number {
    this.seq += 1;
    this.send({ t: "input.submit", text, seq: this.seq });
    return this.seq;
  }
  useItem(item: string): void {
    this.send({ t: "item.use", item });
  }
  qrSolo(
    botLevel: number,
    bots: number,
    contentIds?: number[],
    variant: string = "meaning",
  ): void {
    this.send({
      t: "qr.solo",
      bot_level: botLevel,
      bots,
      content_ids: contentIds,
      variant,
    });
  }
  qrCreate(contentIds?: number[], variant: string = "meaning"): void {
    this.send({ t: "qr.create", content_ids: contentIds, variant });
  }
  qrJoin(code: string): void {
    this.send({ t: "qr.join", code });
  }
  qrStart(): void {
    this.send({ t: "qr.start" });
  }
  qrAnswer(answer: string): void {
    this.send({ t: "qr.answer", answer });
  }
  qrLeave(): void {
    this.send({ t: "qr.leave" });
  }
  tpSolo(): void {
    this.send({ t: "tp.solo" });
  }
  tpCreate(): void {
    this.send({ t: "tp.create" });
  }
  tpJoin(code: string): void {
    this.send({ t: "tp.join", code });
  }
  tpBegin(): void {
    this.send({ t: "tp.begin" });
  }
  tpTyping(idx: number, chars: number): void {
    this.send({ t: "tp.typing", idx, chars });
  }
  tpDone(idx: number, chars: number, errors: number): void {
    this.send({ t: "tp.done", idx, chars, errors });
  }
  tpLeave(): void {
    this.send({ t: "tp.leave" });
  }
  stHost(): void {
    this.send({ t: "st.host" });
  }
  stRequest(code: string): void {
    this.send({ t: "st.request", code });
  }
  stAllow(watcherId: number, allow: boolean): void {
    this.send({ t: "st.allow", watcher_id: watcherId, allow });
  }
  stEvent(payload: object): void {
    // 관전자는 호스트의 테마로 화면을 본다 — 송신부 한 곳에서 자동 동봉
    this.send({ t: "st.event", payload: { ...payload, theme: getAppTheme() } });
  }
  scSolo(): void {
    this.send({ t: "sc.solo" });
  }
  scCreate(): void {
    this.send({ t: "sc.create" });
  }
  scJoin(code: string): void {
    this.send({ t: "sc.join", code });
  }
  scBegin(): void {
    this.send({ t: "sc.begin" });
  }
  scProgress(idx: number, placed: number): void {
    this.send({ t: "sc.progress", idx, placed });
  }
  scDone(idx: number, mistakes: number): void {
    this.send({ t: "sc.done", idx, mistakes });
  }
  scLeave(): void {
    this.send({ t: "sc.leave" });
  }
  dtSolo(): void {
    this.send({ t: "dt.solo" });
  }
  dtCreate(): void {
    this.send({ t: "dt.create" });
  }
  dtJoin(code: string): void {
    this.send({ t: "dt.join", code });
  }
  dtBegin(): void {
    this.send({ t: "dt.begin" });
  }
  dtSubmit(idx: number, text: string): void {
    this.send({ t: "dt.submit", idx, text });
  }
  dtLeave(): void {
    this.send({ t: "dt.leave" });
  }
  stChat(text: string): void {
    this.send({ t: "st.chat", text });
  }
  stCheer(kind: string): void {
    this.send({ t: "st.cheer", kind });
  }
  stLeave(): void {
    this.send({ t: "st.leave" });
  }
  invite(toUserId: number, game: string, code: string): void {
    // 게스트 게임 화면을 초대자 테마로 — 송신부 한 곳에서 자동 동봉 (관전 stEvent 와 동일 패턴)
    this.send({
      t: "iv.invite",
      to_user_id: toUserId,
      game,
      code,
      theme: getAppTheme(),
    });
  }
  close(): void {
    this.ws?.close();
    this.ws = null;
  }
}
