import { defineClientConfig } from 'vuepress/client'
import { defineCatalogInfoGetter } from '@vuepress/plugin-catalog/client'
import { ContentSearchBox } from './components/ContentSearchBox.js'
import './styles/search.scss'

defineCatalogInfoGetter((meta) => {
  const title = meta.title
  const order = meta.order

  if (typeof title !== 'string') {
    return null
  }

  return {
    title,
    order: typeof order === 'number' ? order : undefined,
  }
})

export default defineClientConfig({
  enhance({ app }) {
    app.component('SearchBox', ContentSearchBox)
  },
})
