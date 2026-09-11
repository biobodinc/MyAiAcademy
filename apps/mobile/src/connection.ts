/**
 * Connection model for the mobile controller (spec §6, §52).
 *
 * The phone is never a second AI. It is a client of the user's AI host, and the UI must
 * always say which of these states it is in. Phase 6 fills in pairing and transport;
 * Phase 1 ships the state machine so screens are built against the real vocabulary.
 */

export type ConnectionState =
  | { kind: "unpaired" }
  | { kind: "connecting"; hostName: string }
  | { kind: "connected_local"; hostName: string }
  | { kind: "connected_remote"; hostName: string }
  | { kind: "host_offline"; hostName: string; lastSeen: string | null };

export type ConnectionEvent =
  | { type: "paired"; hostName: string }
  | { type: "local_link_up" }
  | { type: "remote_link_up" }
  | { type: "link_down"; at: string }
  | { type: "unpaired" };

export function reduceConnection(state: ConnectionState, event: ConnectionEvent): ConnectionState {
  switch (event.type) {
    case "paired":
      return { kind: "connecting", hostName: event.hostName };
    case "unpaired":
      return { kind: "unpaired" };
    case "local_link_up":
      return state.kind === "unpaired"
        ? state
        : { kind: "connected_local", hostName: state.hostName };
    case "remote_link_up":
      // A direct local link always wins over a relayed one (spec §18).
      if (state.kind === "unpaired" || state.kind === "connected_local") return state;
      return { kind: "connected_remote", hostName: state.hostName };
    case "link_down":
      return state.kind === "unpaired"
        ? state
        : { kind: "host_offline", hostName: state.hostName, lastSeen: event.at };
  }
}

export function describeConnection(state: ConnectionState): { emoji: string; label: string } {
  switch (state.kind) {
    case "unpaired":
      return { emoji: "⚪", label: "Not paired with a MyAI host" };
    case "connecting":
      return { emoji: "🟡", label: `Connecting to ${state.hostName}` };
    case "connected_local":
      return { emoji: "🟢", label: `Connected locally to ${state.hostName}` };
    case "connected_remote":
      return { emoji: "🟢", label: `Connected remotely to ${state.hostName}` };
    case "host_offline":
      return { emoji: "🔴", label: `${state.hostName} is offline` };
  }
}
