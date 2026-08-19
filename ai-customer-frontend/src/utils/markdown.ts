import MarkdownIt from 'markdown-it'
import markdownItHighlightjs from 'markdown-it-highlightjs'

/** Markdown 渲染器实例（含代码高亮）。 */
const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: false,
}).use(markdownItHighlightjs)

/** 将 Markdown 文本渲染为 HTML。 */
export function renderMarkdown(text: string): string {
  if (!text) return ''
  return md.render(text)
}
