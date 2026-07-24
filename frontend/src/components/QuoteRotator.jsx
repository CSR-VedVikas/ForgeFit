import { useEffect, useState } from 'react'

const QUOTES = [
  // Gym classics
  { text: 'The last three or four reps is what makes the muscle grow.', by: 'Arnold Schwarzenegger' },
  { text: 'I hated every minute of training, but I said, “Don’t quit.”', by: 'Muhammad Ali' },
  { text: 'Somebody may beat me, but they are going to have to bleed to do it.', by: 'Steve Prefontaine' },
  { text: 'The only bad workout is the one that didn’t happen.', by: 'Unknown' },
  { text: 'Pain is temporary. Quitting lasts forever.', by: 'Lance Armstrong' },
  { text: 'We are what we repeatedly do. Excellence, then, is not an act, but a habit.', by: 'Aristotle' },
  { text: 'Strength does not come from winning. Your struggles develop your strengths.', by: 'Arnold Schwarzenegger' },
  { text: 'If it doesn’t challenge you, it doesn’t change you.', by: 'Fred DeVito' },
  { text: 'Don’t count the days, make the days count.', by: 'Muhammad Ali' },
  { text: 'You have to think it before you can do it. The mind is what makes it all possible.', by: 'Kai Greene' },
  // Kobe Bryant — Mamba Mentality
  { text: 'My brain, it cannot process failure. It will not process failure.', by: 'Kobe Bryant' },
  { text: 'If you’re afraid to fail, then you’re probably going to fail.', by: 'Kobe Bryant' },
  { text: 'I have self-doubt… You don’t deny it, but you also don’t capitulate to it. You embrace it.', by: 'Kobe Bryant' },
  { text: 'Great things come from hard work and perseverance. No excuses.', by: 'Kobe Bryant' },
  { text: 'The moment you give up is the moment you let someone else win.', by: 'Kobe Bryant' },
  { text: 'Friends can come and go, but banners hang forever.', by: 'Kobe Bryant' },
  { text: 'I don’t want to be the next Michael Jordan, I only want to be Kobe Bryant.', by: 'Kobe Bryant' },
  { text: 'You are responsible for how people remember you… Leave a legend.', by: 'Kobe Bryant' },
  { text: 'Winning takes precedence over all. There’s no gray area. No almosts.', by: 'Kobe Bryant' },
  { text: 'The most important thing is to try and inspire people so that they can be great in whatever they want to do.', by: 'Kobe Bryant' },
  { text: 'Everything negative — pressure, challenges — is all an opportunity for me to rise.', by: 'Kobe Bryant' },
  { text: 'Once you know what failure feels like, determination chases success.', by: 'Kobe Bryant' },
  { text: 'The most important thing is you must put everybody on notice that you’re here and you are for real.', by: 'Kobe Bryant' },
  { text: 'A lot of leaders fail because they don’t have the bravery to touch that nerve or strike that chord.', by: 'Kobe Bryant' },
  { text: 'Be authentic, and let them like you or not for who you actually are.', by: 'Kobe Bryant' },
  { text: 'I realized that intimidation didn’t really exist if you’re in the right frame of mind.', by: 'Kobe Bryant' },
  { text: 'After all, greatness is not for everybody.', by: 'Kobe Bryant' },
  { text: 'We can always kind of be average and do what’s normal. I’m not in this to do what’s normal.', by: 'Kobe Bryant' },
]

export default function QuoteRotator({ intervalMs = 5500 }) {
  const [i, setI] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setI((x) => (x + 1) % QUOTES.length), intervalMs)
    return () => clearInterval(id)
  }, [intervalMs])

  const q = QUOTES[i]
  return (
    <div className="quote-rotator" key={i}>
      <blockquote>“{q.text}”</blockquote>
      <cite>— {q.by}</cite>
    </div>
  )
}
