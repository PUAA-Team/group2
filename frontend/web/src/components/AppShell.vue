<script setup lang="ts">
import { computed } from "vue";
import { ADMIN_NAV, icon, NAV_GROUPS } from "@live/ui/ui.js";
import { ctx } from "@/stores/app";

const props = defineProps<{
  title: string;
  hasCustomBreadcrumb?: boolean;
}>();

const activePath = computed(() => (ctx.path === "/train/new" ? "/projects" : ctx.path || "/home"));
const isAdmin = computed(() => Boolean(ctx.session?.user?.is_admin));
const userName = computed(() => ctx.session?.user?.display_name || "用户");
const userInitial = computed(() => userName.value.slice(0, 1) || "用");
const platformName = computed(() => ctx.platform?.platform_name || "模训平台");
const environmentLabel = computed(() =>
  ["localhost", "127.0.0.1", "::1", "[::1]"].includes(location.hostname) ? "本机环境" : "服务器环境"
);

function isGroupActive(children: string[][]) {
  return children.some(([, href]) => activePath.value === href || activePath.value.startsWith(`${href}/`));
}

function isLinkActive(href: string) {
  return activePath.value === href || activePath.value.startsWith(`${href}/`);
}
</script>

<template>
  <div
    id="shell"
    class="app-shell"
    :class="{ 'sidebar-collapsed': ctx.ui.sidebarCollapsed, 'menu-open': ctx.ui.menuOpen }"
    :inert="Boolean(ctx.ui.modal)"
  >
    <header class="topbar">
      <div class="topbar-left">
        <button class="icon-button mobile-menu" aria-label="打开菜单" data-action="open-menu" v-html="icon('menu')" />
        <a class="console-brand" href="#/home">
          <span class="brand-mark" v-html="icon('models', 22)" />
          <strong>{{ platformName }}</strong>
        </a>
        <span class="product-name">AI 开发控制台</span>
      </div>
      <div class="topbar-right">
        <select
          class="select live-workspace-select"
          data-workspace-select
          aria-label="当前工作空间"
          :value="ctx.ui.workspaceId"
        >
          <option v-if="!ctx.workspaces.length" value="">暂无工作空间</option>
          <option v-for="space in ctx.workspaces" :key="space.id" :value="space.id">{{ space.name }}</option>
        </select>
        <span class="environment-badge">{{ environmentLabel }}</span>
        <span class="topbar-user">{{ userName }}</span>
        <span class="avatar avatar-small">{{ userInitial }}</span>
        <button
          class="icon-button"
          title="退出登录"
          aria-label="退出登录"
          data-action="logout"
          v-html="icon('arrow', 16)"
        />
      </div>
    </header>

    <div class="sidebar-overlay" data-action="close-menu" />

    <aside class="sidebar" aria-label="主导航">
      <div class="nav-product">
        <strong>模型开发</strong>
        <button
          class="icon-button desktop-collapse"
          title="展开或收起侧栏"
          aria-label="展开或收起侧栏"
          :aria-expanded="!ctx.ui.sidebarCollapsed"
          data-action="collapse-sidebar"
          v-html="icon('menu', 17)"
        />
        <button class="icon-button mobile-close" aria-label="关闭菜单" data-action="close-menu" v-html="icon('close')" />
      </div>

      <nav class="sidebar-nav">
        <div
          v-for="group in NAV_GROUPS"
          :key="group.id"
          class="nav-section"
          :class="{ open: ctx.ui.navOpen[group.id] !== false }"
        >
          <button
            type="button"
            class="nav-parent"
            :class="{ current: isGroupActive(group.children) }"
            data-action="toggle-nav"
            :data-group="group.id"
            :aria-expanded="ctx.ui.navOpen[group.id] !== false"
            :aria-label="group.label"
            :title="group.label"
          >
            <span v-html="icon(group.icon)" />
            <span class="nav-label">{{ group.label }}</span>
            <span v-html="icon('chevron', 14)" />
          </button>
          <div class="nav-children">
            <a
              v-for="[label, href] in group.children"
              :key="href"
              class="nav-child"
              :class="{ active: isLinkActive(href) }"
              :href="`#${href}`"
              :aria-current="activePath === href ? 'page' : undefined"
            >
              {{ label }}
            </a>
          </div>
        </div>

        <template v-if="isAdmin">
          <div class="nav-divider"><span>管理端</span></div>
          <a
            v-for="[label, href, symbol] in ADMIN_NAV"
            :key="href"
            class="nav-link"
            :class="{ active: activePath === href }"
            :href="`#${href}`"
            :aria-current="activePath === href ? 'page' : undefined"
            :title="label"
          >
            <span v-html="icon(symbol)" />
            <span class="nav-label">{{ label }}</span>
          </a>
        </template>
      </nav>

      <a class="sidebar-bottom" href="#/space" title="用户空间">
        <span v-html="icon('users', 17)" />
        <span class="nav-label">用户空间</span>
      </a>
    </aside>

    <main class="main-area">
      <div class="content">
        <div v-if="!hasCustomBreadcrumb" class="console-crumb">
          <a href="#/home">研发空间</a>
          <span>/</span>
          <span>{{ props.title }}</span>
        </div>
        <div class="page-surface">
          <slot />
        </div>
      </div>
    </main>
  </div>
</template>
