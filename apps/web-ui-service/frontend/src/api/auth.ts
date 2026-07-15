import { getJson, postJson } from "../lib/http";

export interface AuthUser {
  user_public_id: string;
  username: string;
  role: string;
  is_active: boolean;
  created_at?: string | null;
}

export interface LoginPayload {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token?: string;
  user?: AuthUser;
}

export async function login(payload: LoginPayload): Promise<LoginResponse> {
  return postJson<LoginResponse>("/api/auth/login", payload);
}

export async function getCurrentUser(): Promise<AuthUser> {
  return getJson<AuthUser>("/api/auth/me");
}
