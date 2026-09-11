import { describe, expect, it } from "vitest";

import { describeConnection, reduceConnection, type ConnectionState } from "../src/connection";

describe("reduceConnection", () => {
  it("pairs, connects locally, then reports offline", () => {
    let s: ConnectionState = { kind: "unpaired" };
    s = reduceConnection(s, { type: "paired", hostName: "Gaming PC" });
    expect(s.kind).toBe("connecting");
    s = reduceConnection(s, { type: "local_link_up" });
    expect(s.kind).toBe("connected_local");
    s = reduceConnection(s, { type: "link_down", at: "2026-09-11T00:00:00Z" });
    expect(s).toEqual({
      kind: "host_offline",
      hostName: "Gaming PC",
      lastSeen: "2026-09-11T00:00:00Z",
    });
  });

  it("prefers a local link over a remote one", () => {
    const local: ConnectionState = { kind: "connected_local", hostName: "PC" };
    expect(reduceConnection(local, { type: "remote_link_up" })).toEqual(local);
    const connecting: ConnectionState = { kind: "connecting", hostName: "PC" };
    expect(reduceConnection(connecting, { type: "remote_link_up" }).kind).toBe("connected_remote");
  });

  it("ignores link events while unpaired", () => {
    const s: ConnectionState = { kind: "unpaired" };
    expect(reduceConnection(s, { type: "local_link_up" })).toEqual(s);
    expect(describeConnection(s).label).toMatch(/Not paired/);
  });
});
