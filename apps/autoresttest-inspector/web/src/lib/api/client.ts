import { ZodSchema } from "zod";

export class ApiClientError extends Error {
  readonly status: number;
  readonly payload?: unknown;

  constructor(message: string, status: number, payload?: unknown) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

async function parseError(response: Response): Promise<never> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = await response.text();
  }

  const errorMessage =
    typeof payload === "object" &&
    payload !== null &&
    "error" in payload &&
    typeof (payload as { error?: { message?: unknown } }).error?.message === "string"
      ? (payload as { error: { message: string } }).error.message
      : response.statusText;

  throw new ApiClientError(errorMessage || "Request failed.", response.status, payload);
}

export async function fetchApi<T>(
  path: string,
  schema: ZodSchema<T>,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    await parseError(response);
  }

  const payload = await response.json();
  return schema.parse(payload);
}
