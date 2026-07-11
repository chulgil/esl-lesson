/** 워드 테트리스 WS 클라이언트 (docs/specs/word-tetris.md 프로토콜) */

export interface BrickState {
  id: number;
  display: string;
  y: number;
  landed: boolean;
  garbage: boolean;
}

export interface BoardState {
  bricks: BrickState[];
  combo: number;
  score: number;
  speed_level: number;
  danger: boolean;
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
}

export interface MatchPlayerStats {
  score: number;
  cleared: number;
  misses: number;
  max_combo: number;
  wpm: number;
  accuracy: number;
}

export type ServerMsg =
  | StateMsg
  | MatchFoundMsg
  | ClearResultMsg
  | MatchEndMsg
  | { t: "queue.waiting" }
  | { t: "room.created"; code: string }
  | { t: "attack.recv"; count: number }
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

  joinPve(quiz: string, botLevel: number): void {
    this.send({ t: "queue.join", mode: "pve", quiz, bot_level: botLevel });
  }
  joinPvp(quiz: string): void {
    this.send({ t: "queue.join", mode: "pvp", quiz });
  }
  leaveQueue(): void {
    this.send({ t: "queue.leave" });
  }
  createRoom(quiz: string): void {
    this.send({ t: "room.create", quiz });
  }
  joinRoom(code: string): void {
    this.send({ t: "room.join", code });
  }
  submit(text: string): number {
    this.seq += 1;
    this.send({ t: "input.submit", text, seq: this.seq });
    return this.seq;
  }
  close(): void {
    this.ws?.close();
    this.ws = null;
  }
}
