import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import ChatView from './views/ChatView.vue'
import ComposeView from './views/ComposeView.vue'
import ContainersView from './views/ContainersView.vue'
import DashboardView from './views/DashboardView.vue'
import HistoryView from './views/HistoryView.vue'
import ImagesView from './views/ImagesView.vue'
import NetworksView from './views/NetworksView.vue'
import SettingsView from './views/SettingsView.vue'
import VolumesView from './views/VolumesView.vue'
import './styles/global.css'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: DashboardView },
    { path: '/containers', name: 'containers', component: ContainersView },
    { path: '/images', name: 'images', component: ImagesView },
    { path: '/networks', name: 'networks', component: NetworksView },
    { path: '/volumes', name: 'volumes', component: VolumesView },
    { path: '/compose', name: 'compose', component: ComposeView },
    { path: '/chat', name: 'chat', component: ChatView },
    { path: '/history', name: 'history', component: HistoryView },
    { path: '/settings', name: 'settings', component: SettingsView },
  ],
})

createApp(App).use(router).mount('#app')
