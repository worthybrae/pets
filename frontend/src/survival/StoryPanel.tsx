import { createPortal } from 'react-dom'
import type { DiaryEntry } from './bondTypes'
import { useEscape } from './escape'
import { diaryDay } from './story'

/** "While you were away": the newest story, shown first when the viewer opens while it is unread. Bond's final
 * fix wave: it scrolls within the screen on a phone (m5), and Escape closes it. */
export default function StoryPanel({ name, story, onDiary, onClose }: {
  name: string
  story: DiaryEntry
  onDiary: () => void
  onClose: () => void
}) {
  useEscape(onClose)
  return createPortal(
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-[#203b38]/45 p-4" role="presentation" onClick={onClose}>
      <section role="dialog" aria-modal="true" aria-label="While you were away" onClick={(event) => event.stopPropagation()}
        className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-3xl bg-[#f5faf7] p-6 text-[#243e3d] shadow-2xl sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">While you were away</p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight">{name}'s diary · {diaryDay(story)}</h2>
        <p className="mt-4 text-base leading-7 text-[#315e58]">{story.text}</p>
        <div className="mt-6 flex flex-col gap-2 sm:flex-row">
          <button type="button" onClick={onDiary}
            className="flex-1 rounded-xl border border-[#bfd5cd] px-4 py-2.5 text-sm font-medium text-[#315e58] hover:bg-white">Read the diary</button>
          <button type="button" onClick={onClose}
            className="flex-1 rounded-xl bg-[#315e58] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#244b47]">Back to {name}</button>
        </div>
      </section>
    </div>,
    document.body,
  )
}
