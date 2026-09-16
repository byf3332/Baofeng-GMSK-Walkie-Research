import { computed, defineComponent, h, ref, watch } from 'vue'
import { useRouteLocale, useRouter } from 'vuepress/client'
import {
  isQueryMatched,
  useSearchIndex,
  useSuggestionsFocus,
} from '@vuepress/plugin-search/client'

interface SearchResult {
  link: string
  title: string
  header?: string
  excerpt?: string
}

const flattenHeaders = (
  headers: ReturnType<typeof useSearchIndex>['value'][number]['headers'],
): Array<{ title: string; slug: string }> =>
  headers.flatMap((header) => [
    { title: header.title, slug: header.slug },
    ...flattenHeaders(header.children),
  ])

const cleanLine = (line: string): string =>
  line
    .replace(/^\s*[|>-]+\s*/u, '')
    .replace(/\s*\|\s*/gu, ' · ')
    .replace(/[`*_]/gu, '')
    .trim()

const findContentMatches = (
  content: string,
  query: string,
  headers: Array<{ title: string; slug: string }>,
): Array<Pick<SearchResult, 'excerpt' | 'header' | 'link'>> => {
  const matches: Array<Pick<SearchResult, 'excerpt' | 'header' | 'link'>> = []
  let offset = 0

  for (const line of content.split('\n')) {
    if (line.toLocaleLowerCase().includes(query.toLocaleLowerCase())) {
      const precedingContent = content.slice(0, offset)
      const headingMatches = [...precedingContent.matchAll(/^#{2,6}\s+(.+)$/gmu)]
      const headerTitle = headingMatches.at(-1)?.[1]?.trim()
      const header = headers.find(({ title }) => title === headerTitle)

      matches.push({
        excerpt: cleanLine(line),
        header: header?.title,
        link: header ? `#${header.slug}` : '',
      })
    }
    offset += line.length + 1
  }

  return matches
}

export const ContentSearchBox = defineComponent({
  name: 'ContentSearchBox',

  setup() {
    const router = useRouter()
    const routeLocale = useRouteLocale()
    const searchIndex = useSearchIndex()
    const query = ref('')
    const isActive = ref(false)
    const expanded = ref(false)
    const maxSuggestions = 10

    const results = computed<SearchResult[]>(() => {
      const searchText = query.value.trim()
      if (!searchText) return []

      const matches: SearchResult[] = []
      for (const item of searchIndex.value) {
        if (item.pathLocale !== routeLocale.value) continue

        const headers = flattenHeaders(item.headers)
        const contentMatches = item.extraFields.flatMap((content) =>
          findContentMatches(content, searchText, headers),
        )

        if (contentMatches.length > 0) {
          for (const contentMatch of contentMatches) {
            matches.push({
              title: item.title,
              header: contentMatch.header,
              excerpt: contentMatch.excerpt,
              link: `${item.path}${contentMatch.link}`,
            })
          }
        } else if (isQueryMatched(searchText.toLocaleLowerCase(), [item.title])) {
          matches.push({ link: item.path, title: item.title })
        } else {
          const header = headers.find(({ title }) =>
            isQueryMatched(searchText.toLocaleLowerCase(), [title]),
          )
          if (header) {
            matches.push({
              link: `${item.path}#${header.slug}`,
              title: item.title,
              header: header.title,
            })
          }
        }

      }
      return matches
    })

    const visibleResults = computed(() =>
      expanded.value ? results.value : results.value.slice(0, maxSuggestions),
    )
    const hasMore = computed(
      () => !expanded.value && results.value.length > maxSuggestions,
    )
    const { focusIndex, focusNext, focusPrev } = useSuggestionsFocus(visibleResults)
    const showResults = computed(() => isActive.value && results.value.length > 0)

    watch(query, () => {
      expanded.value = false
      focusIndex.value = 0
    })

    const openResult = (index: number): void => {
      const result = visibleResults.value[index]
      if (!result) return
      void router.push(result.link).then(() => {
        query.value = ''
        focusIndex.value = 0
      })
    }

    return () =>
      h('form', { class: 'search-box content-search-box', role: 'search' }, [
        h('input', {
          type: 'search',
          placeholder: routeLocale.value === '/en/' ? 'Search' : '搜索',
          autocomplete: 'off',
          spellcheck: false,
          value: query.value,
          onFocus: () => {
            isActive.value = true
          },
          onBlur: () => {
            isActive.value = false
          },
          onInput: (event: Event) => {
            query.value = (event.target as HTMLInputElement).value
          },
          onKeydown: (event: KeyboardEvent) => {
            if (event.key === 'ArrowUp') {
              event.preventDefault()
              focusPrev()
            } else if (event.key === 'ArrowDown') {
              event.preventDefault()
              focusNext()
            } else if (event.key === 'Enter') {
              event.preventDefault()
              openResult(focusIndex.value)
            }
          },
        }),
        showResults.value &&
          h(
            'ul',
            { class: 'suggestions' },
            [
              ...visibleResults.value.map((result, index) =>
              h(
                'li',
                {
                  class: ['suggestion', { focus: focusIndex.value === index }],
                  onMouseenter: () => {
                    focusIndex.value = index
                  },
                  onMousedown: () => openResult(index),
                },
                h(
                  'a',
                  {
                    href: result.link,
                    onClick: (event: Event) => event.preventDefault(),
                  },
                  [
                    h('span', { class: 'page-title' }, result.title),
                    result.header &&
                      h('span', { class: 'page-header' }, `> ${result.header}`),
                    result.excerpt &&
                      h('span', { class: 'page-excerpt' }, result.excerpt),
                  ],
                ),
              ),
              ),
              hasMore.value &&
                h(
                  'li',
                  {
                    class: 'search-more',
                    onMousedown: (event: MouseEvent) => {
                      event.preventDefault()
                      expanded.value = true
                    },
                  },
                  h('button', { type: 'button' }, '...还有更多'),
                ),
            ],
          ),
      ])
  },
})
