import { addUser, currentUser, findAccount, registerUser, setSessionUserId } from "./state.js?v=console-4";

const DEMO_PASSWORDS = { "admin@example.test": "Admin123!", "lin@example.test": "Demo123!", "zhou@example.test": "Demo123!", "viewer@example.test": "Demo123!" };

async function digest(password, salt) {
  const bytes = new TextEncoder().encode(`${salt}:${password}`);
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(hash), value => value.toString(16).padStart(2, "0")).join("");
}

export async function login(account, password) {
  const user = findAccount(account);
  if (!user || user.status !== "启用") return { ok: false, message: "账号不存在或已停用" };
  const valid = user.passwordHash ? await digest(password, user.salt) === user.passwordHash : DEMO_PASSWORDS[user.account] === password;
  if (!valid) return { ok: false, message: "密码不正确" };
  setSessionUserId(user.id);
  return { ok: true, user };
}

export async function register({ name, account, password }) {
  if (findAccount(account)) return { ok: false, message: "该邮箱已注册" };
  const salt = crypto.randomUUID();
  const user = registerUser({ name, account, salt, passwordHash: await digest(password, salt) });
  setSessionUserId(user.id);
  return { ok: true, user };
}

export async function createUser({ name, account, password, groupId }) {
  if (currentUser()?.role !== "管理员") return { ok: false, message: "无权创建用户" };
  if (findAccount(account)) return { ok: false, message: "该邮箱已存在" };
  if (password.length < 8) return { ok: false, message: "初始密码至少 8 位" };
  const salt = crypto.randomUUID();
  const user = addUser({ name, account, groupId, salt, passwordHash: await digest(password, salt) });
  return user ? { ok: true, user } : { ok: false, message: "用户组无效" };
}

export function logout() { setSessionUserId(null); }
export { currentUser };
