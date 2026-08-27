import crypto from "node:crypto";
import fs from "node:fs";
import { DatabaseSync } from "node:sqlite";
import express, { NextFunction, Request, Response } from "express";

const PORT = Number(process.env.PORT || "3000");
const DB_PATH = process.env.FANZ_SUI_DB_PATH || "/data/fanz-sui.sqlite3";
const API_TOKEN = process.env.FANZ_SUI_API_TOKEN || "";

if (!API_TOKEN) {
  throw new Error("FANZ_SUI_API_TOKEN is required");
}

fs.mkdirSync(new URL(".", `file://${DB_PATH}`).pathname, {
  recursive: true,
});

const db = new DatabaseSync(DB_PATH);

db.exec(`
  PRAGMA journal_mode = WAL;

  CREATE TABLE IF NOT EXISTS deliveries (
    submission_key TEXT PRIMARY KEY,
    chain TEXT NOT NULL,
    coin_type TEXT NOT NULL,
    recipient_address TEXT NOT NULL,
    amount_base_units TEXT NOT NULL,
    state TEXT NOT NULL,
    sender_address TEXT,
    tx_digest TEXT UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
  );
`);

type DeliveryInput = {
  submission_key: string;
  chain: string;
  coin_type: string;
  recipient_address: string;
  amount_base_units: string;
};

type DeliveryRow = DeliveryInput & {
  state: string;
  sender_address: string | null;
  tx_digest: string | null;
  created_at: string;
  updated_at: string;
};

function constantTimeTokenMatch(provided: string): boolean {
  const expected = Buffer.from(API_TOKEN);
  const actual = Buffer.from(provided);

  if (expected.length !== actual.length) {
    return false;
  }

  return crypto.timingSafeEqual(expected, actual);
}

function authenticate(
  req: Request,
  res: Response,
  next: NextFunction,
): void {
  const header = req.header("authorization") || "";
  const prefix = "Bearer ";

  if (
    !header.startsWith(prefix) ||
    !constantTimeTokenMatch(header.slice(prefix.length))
  ) {
    res.status(401).json({ error: "unauthorized" });
    return;
  }

  next();
}

function validateDelivery(body: unknown): DeliveryInput {
  if (!body || typeof body !== "object") {
    throw new Error("request body must be an object");
  }

  const value = body as Record<string, unknown>;

  const required = [
    "submission_key",
    "chain",
    "coin_type",
    "recipient_address",
    "amount_base_units",
  ] as const;

  for (const key of required) {
    if (
      typeof value[key] !== "string" ||
      value[key].trim() === ""
    ) {
      throw new Error(`${key} must be a non-empty string`);
    }
  }

  if (!/^[0-9]+$/.test(value.amount_base_units as string)) {
    throw new Error("amount_base_units must be a positive integer string");
  }

  if (BigInt(value.amount_base_units as string) <= 0n) {
    throw new Error("amount_base_units must be positive");
  }

  return {
    submission_key: value.submission_key as string,
    chain: value.chain as string,
    coin_type: value.coin_type as string,
    recipient_address: value.recipient_address as string,
    amount_base_units: value.amount_base_units as string,
  };
}

function getDelivery(submissionKey: string): DeliveryRow | undefined {
  return db.prepare(`
    SELECT
      submission_key,
      chain,
      coin_type,
      recipient_address,
      amount_base_units,
      state,
      sender_address,
      tx_digest,
      created_at,
      updated_at
    FROM deliveries
    WHERE submission_key = ?
  `).get(submissionKey) as DeliveryRow | undefined;
}

function immutableFieldsMatch(
  existing: DeliveryRow,
  requested: DeliveryInput,
): boolean {
  return (
    existing.chain === requested.chain &&
    existing.coin_type === requested.coin_type &&
    existing.recipient_address === requested.recipient_address &&
    existing.amount_base_units === requested.amount_base_units
  );
}

const app = express();

app.disable("x-powered-by");
app.use(express.json({ limit: "32kb" }));

app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    service: "fanz-sui",
    adapter: "mock",
  });
});

app.use("/v1", authenticate);

app.post("/v1/deliveries", (req, res) => {
  let requested: DeliveryInput;

  try {
    requested = validateDelivery(req.body);
  } catch (error) {
    res.status(400).json({
      error: error instanceof Error ? error.message : "invalid request",
    });
    return;
  }

  const existing = getDelivery(requested.submission_key);

  if (existing) {
    if (!immutableFieldsMatch(existing, requested)) {
      res.status(409).json({
        error: "submission_key already exists with different immutable data",
        delivery: existing,
      });
      return;
    }

    res.json({
      created: false,
      delivery: existing,
    });
    return;
  }

  const now = new Date().toISOString();

  // Mock-only public sender identity.
  // No private key and no chain transaction exist in v0.
  const senderAddress =
    "mock:" +
    crypto
      .createHash("sha256")
      .update(requested.submission_key)
      .digest("hex")
      .slice(0, 32);

  db.prepare(`
    INSERT INTO deliveries (
      submission_key,
      chain,
      coin_type,
      recipient_address,
      amount_base_units,
      state,
      sender_address,
      tx_digest,
      created_at,
      updated_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
  `).run(
    requested.submission_key,
    requested.chain,
    requested.coin_type,
    requested.recipient_address,
    requested.amount_base_units,
    "prepared",
    senderAddress,
    now,
    now,
  );

  res.status(201).json({
    created: true,
    delivery: getDelivery(requested.submission_key),
  });
});

app.get("/v1/deliveries/:submissionKey", (req, res) => {
  const delivery = getDelivery(req.params.submissionKey);

  if (!delivery) {
    res.status(404).json({ error: "delivery not found" });
    return;
  }

  res.json({ delivery });
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`fanz-sui mock adapter listening on ${PORT}`);
});
