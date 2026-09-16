import { defineUserConfig } from 'vuepress'
import { viteBundler } from '@vuepress/bundler-vite'
import { defaultTheme } from '@vuepress/theme-default'
import { searchPlugin } from '@vuepress/plugin-search'
import { catalogPlugin } from '@vuepress/plugin-catalog'

export default defineUserConfig({
  locales: {
    '/': {
      lang: 'zh-CN',
      title: '宝锋 GMSK 对讲机读写频通信协议',
    },
    '/en/': {
      lang: 'en-US',
      title: 'Baofeng GMSK Radio Programming Communication Protocol',
    },
  },

  base: process.env.NODE_ENV === 'production'
    ? '/Baofeng-GMSK-Walkie-Research/'
    : '/',

  bundler: viteBundler(),

  extendsPage: (page) => {
    const order = page.frontmatter.order

    page.routeMeta = {
      title: page.title,
      order: typeof order === 'number' ? order : undefined,
    }
  },

  theme: defaultTheme({
    lastUpdated: false,
    contributors: false,
    themePlugins: {
      git: false,
    },
    locales: {
      '/': {
        selectLanguageName: '简体中文',
        navbar: [
          { text: '首页', link: '/' },
          { text: '协议', link: '/protocols/' },
        ],
        sidebar: {
          '/': [
            {
              text: '协议',
              link: '/protocols/',
              children: [
                {
                  text: 'Protocol A',
                  link: '/protocol-a/',
                  children: [
                    '/protocol-a/handshake.md',
                    '/protocol-a/clone.md',
                    '/protocol-a/settings.md',
                    '/protocol-a/password-subsystem-id.md',
                  ],
                },
                { text: 'Protocol B', link: '/protocol-b/' },
                { text: 'Protocol C', link: '/protocol-c/' },
                { text: 'Protocol D', link: '/protocol-d/' },
                { text: 'Protocol E', link: '/protocol-e/' },
                { text: 'Protocol F', link: '/protocol-f/' },
                {
                  text: 'AT2',
                  link: '/protocol-at2/',
                  children: [
                    '/protocol-at2/transport.md',
                    '/protocol-at2/frame.md',
                    '/protocol-at2/channel.md',
                    '/protocol-at2/settings.md',
                    '/protocol-at2/offline-message.md',
                    '/protocol-at2/realtime-voice.md',
                  ],
                },
              ],
            },
          ],
        },
      },
      '/en/': {
        selectLanguageName: 'English',
        navbar: [
          { text: 'Home', link: '/en/' },
          { text: 'Protocols', link: '/en/protocols/' },
        ],
        sidebar: {
          '/en/': [
            {
              text: 'Protocols',
              link: '/en/protocols/',
              children: [
                {
                  text: 'Protocol A',
                  link: '/en/protocol-a/',
                  children: [
                    '/en/protocol-a/handshake.md',
                    '/en/protocol-a/clone.md',
                    '/en/protocol-a/settings.md',
                    '/en/protocol-a/password-subsystem-id.md',
                  ],
                },
                { text: 'Protocol B', link: '/en/protocol-b/' },
                { text: 'Protocol C', link: '/en/protocol-c/' },
                { text: 'Protocol D', link: '/en/protocol-d/' },
                { text: 'Protocol E', link: '/en/protocol-e/' },
                { text: 'Protocol F', link: '/en/protocol-f/' },
                {
                  text: 'AT2',
                  link: '/en/protocol-at2/',
                  children: [
                    '/en/protocol-at2/transport.md',
                    '/en/protocol-at2/frame.md',
                    '/en/protocol-at2/channel.md',
                    '/en/protocol-at2/settings.md',
                    '/en/protocol-at2/offline-message.md',
                    '/en/protocol-at2/realtime-voice.md',
                  ],
                },
              ],
            },
          ],
        },
      },
    },
  }),

  plugins: [
    searchPlugin({
      locales: {
        '/': {
          placeholder: '搜索',
        },
        '/en/': {
          placeholder: 'Search',
        },
      },
      maxSuggestions: 10,
      getExtraFields: (page) => [page.content],
    }),

    catalogPlugin({
      locales: {
        '/': {
          title: '目录',
          empty: '暂无页面',
        },
        '/en/': {
          title: 'Catalog',
          empty: 'No pages',
        },
      },
    }),
  ],
})
