<template>
  <el-container class="app-container">
    <el-aside width="200px" class="aside">
      <div class="logo">票据识别</div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
      >
        <el-menu-item index="/documents">
          <el-icon><Document /></el-icon>
          <span>票据识别</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = computed(() => route.path)
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #app { height: 100%; }
.app-container { height: 100%; }
.aside {
  background: #304156;
  color: #bfcbd9;
}
.logo {
  height: 50px;
  line-height: 50px;
  text-align: center;
  color: #fff;
  font-weight: 600;
  font-size: 16px;
}
.main {
  background: #f0f2f5;
  padding: 20px;
  overflow: auto;
}
</style>
