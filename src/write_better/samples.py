"""A representative sample input for every service.

The browser UI's "Try a sample" button loads these so a user can see what each
service does without supplying their own text. Each sample is chosen to clearly
exercise the service it belongs to. Keyed by service name (see ``modes.py``).
"""

SAMPLES: dict[str, str] = {
    # --- core modes (A-M) ---
    "write": (
        "Brief: Announce a 20% summer sale on all running shoes to our newsletter "
        "subscribers. Friendly and a little urgent. One short paragraph with a clear "
        "call to action."
    ),
    "correct": (
        "Their going too the store on tuesday, but they forgot they're wallet and the "
        "shop dont open untill nine oclock."
    ),
    "clarify": (
        "The thing about the new process is that it sort of takes the data and does "
        "stuff to it and then the results come out, which is basically what the team "
        "wanted to happen in the end."
    ),
    "tighten": (
        "At this point in time, due to the fact that the quarterly report was extremely "
        "long and detailed in nature, we ultimately came to the decision to summarize it "
        "down in order to save everyone a lot of valuable time."
    ),
    "retone": (
        "Hey — the invoice is super late AGAIN and honestly it's getting really "
        "annoying. Can you just pay it already? Thanks."
    ),
    "paraphrase": (
        "The early bird catches the worm, so getting started on your project sooner "
        "rather than later gives you a real edge over the competition."
    ),
    "level": (
        "Mitochondria are membrane-bound organelles that generate most of the cell's "
        "supply of ATP through oxidative phosphorylation, leveraging the electron "
        "transport chain across the inner mitochondrial membrane."
    ),
    "resize": (
        "Our app helps you track expenses."
    ),
    "summarize": (
        "The committee met on Thursday to review the budget. After two hours of "
        "discussion, members agreed to cut travel spending by 15%, delay the office "
        "renovation to next year, and reallocate the savings to the engineering team's "
        "hiring plan. A follow-up vote is scheduled for next month."
    ),
    "translate": (
        "Could you send me the final version of the contract before the end of the day? "
        "I'd like to review it tonight."
    ),
    "structure": (
        "Our onboarding has three parts. First, account setup, where you create a profile "
        "and connect your email. Then configuration, you set your preferences and import "
        "data. Finally, the walkthrough, a short tour of the main features. Support is "
        "available at any step."
    ),
    "convert": (
        "Subject: Project update. Hi team, the launch is on track for March 10. QA "
        "finishes Friday, marketing assets are ready, and we'll do a final review Monday. "
        "Reach out with any questions."
    ),
    "check": (
        "Our innovative solution leverages cutting-edge synergies to deliver impactful, "
        "best-in-class outcomes that move the needle for stakeholders going forward."
    ),
    # --- extended services ---
    "tone-detect": (
        "We regret to inform you that your application was not successful on this "
        "occasion. We received many strong submissions and the decision was extremely "
        "difficult. We wish you the very best in your future endeavors."
    ),
    "readability": (
        "Notwithstanding the aforementioned considerations, the implementation of the "
        "proposed methodology necessitates a comprehensive re-evaluation of the extant "
        "operational paradigms, the ramifications of which extend considerably beyond the "
        "immediate purview of the department."
    ),
    "detect-weak": (
        "It is believed by the team that the results were impacted by the changes that "
        "were made, and it could possibly be the case that further investigation might be "
        "needed in order to make a determination."
    ),
    "consistency": (
        "We e-mailed the customer about the colour of the 5 items, then emailed again "
        "about the color of five more. The organisation's policy on email formatting is "
        "being organized by the team."
    ),
    "inclusive": (
        "Every developer should bring his laptop. We need a sanity check from the guys "
        "before the crazy deadline, and the new salesman will man the booth."
    ),
    "style-issues": (
        "At the end of the day, we need to think outside the box and leverage our core "
        "competencies to move the needle, circle back, and take this to the next level in "
        "a truly paradigm-shifting way."
    ),
    "flow": (
        "The team met. The plan was set. The work began. The deadline loomed. The team "
        "worked hard. The product shipped. The users came. The team rested at last."
    ),
    "originality": (
        "It was the best of times, it was the worst of times. A journey of a thousand "
        "miles begins with a single step, and at the end of the day, only time will tell."
    ),
    "humanize": (
        "Leveraging a robust framework, our solution not only optimizes efficiency but "
        "also enhances scalability. Furthermore, it is important to note that the "
        "synergistic integration delivers measurable value. In conclusion, stakeholders "
        "will benefit significantly."
    ),
    "fact-flag": (
        "The Great Wall of China is the only man-made structure visible from space. "
        "Founded in 1923, the company now serves over 10 billion customers across 250 "
        "countries, and studies show 99% of users prefer it to every alternative."
    ),
    "cite": (
        "Source 1: Jane Smith, book 'Writing Well', published 2019 by Penguin, page 42. "
        "Source 2: John Doe, 2021 article 'Clarity in Prose', Journal of Style, volume 12, "
        "pages 5-20. Please format these in APA, with in-text citations and a reference "
        "list."
    ),
    "variations": (
        "We should probably consider rescheduling the meeting to a later date if everyone "
        "is okay with that."
    ),
    "enhance-vocab": (
        "The report was good and had a lot of good points, and the data was good, which "
        "made the conclusion good and easy to understand."
    ),
    "paraphrase-modes": (
        "Mode: formal\n\n"
        "Hey, just wanted to give you a heads up that the thing you asked about is "
        "basically done, so we can chat about it whenever you're free."
    ),
    "fluency": (
        "I am working in this company since three years. Yesterday I have finished the "
        "project what you give me, and I am thinking it will make good impression to the "
        "client."
    ),
    "headline": (
        "A blog post about five simple habits that help remote workers stay focused and "
        "avoid burnout during long workdays at home."
    ),
    "outline": (
        "A practical guide for first-time home buyers covering budgeting, getting a "
        "mortgage, finding the right home, making an offer, and closing the deal."
    ),
    "brainstorm": (
        "Content ideas for a small specialty coffee roaster's Instagram account that "
        "wants to grow a loyal local following."
    ),
    "template": (
        "Product: a reusable stainless-steel water bottle that keeps drinks cold for 24 "
        "hours, is fully leak-proof, and costs $29. Write a short product description and "
        "a social post."
    ),
    "fiction": (
        "describe\n\n"
        "The old lighthouse stood at the edge of the cliff. Mara climbed the last few "
        "steps and pushed open the heavy door."
    ),
    "brand-voice": (
        "Style guide: warm but professional; never use 'utilize' (use 'use'); avoid "
        "exclamation points; prefer 'customers' over 'users'.\n\n"
        "Text: Hey users!! We're super excited to utilize our brand-new feature to help "
        "you out!!"
    ),
    "explain": (
        "Me and him went to the meeting, but the report were not ready, so we had went "
        "back to the office to wait for it's completion."
    ),
    "score": (
        "Our app is good and helps people do tasks. It has many features that are useful. "
        "Users can do things easily. We think you will like it because it is helpful and "
        "nice to use."
    ),
    "reply": (
        "Hi — thanks for sending over the proposal. The scope looks good, but the timeline "
        "is tight on our end and the price is a little above what we budgeted. Could you "
        "deliver by the end of next month, and is there any flexibility on cost? Let me "
        "know what's possible. — Dana"
    ),
    "send-check": (
        "This is the THIRD time the invoice has been late and frankly it's getting "
        "ridiculous. If I don't see payment by tomorrow I'm done working with you people. "
        "Just sort it out already."
    ),
    "confidential": (
        "Hi team — forwarding the notes from the board call. Our Q3 revenue was $4.2M "
        "(still confidential), and we're acquiring Project Falcon next month. Reach Maria "
        "Lopez at maria.lopez@example.com or 415-555-0148 if you have questions."
    ),
    "dictate": (
        "um so yeah i was thinking like maybe we could uh move the meeting to thursday "
        "because friday is you know kind of packed and i mean i have the dentist thing "
        "anyway so like thursday afternoon would be way better i think and also can you uh "
        "bring the the budget numbers the q3 ones"
    ),
    "merge": (
        "=== SOURCE 1 ===\n"
        "Team synced on the launch. We agreed to ship the beta on March 10 and cap it "
        "at 50 users. Marketing drafts the announcement.\n\n"
        "=== SOURCE 2 ===\n"
        "Launch notes: beta goes out mid-March to a small group (~50 people). Hold the "
        "press release until general availability, not the beta."
    ),
    "wordfinder": (
        "What's the word for the bittersweet awareness that something good is happening "
        "even as you realize it's already slipping into the past?"
    ),
    "argument-check": (
        "We must ban all cars from downtown immediately. Traffic is terrible, and everyone "
        "knows cars cause pollution. The cities that did this are thriving. If we don't act "
        "now, downtown will die. Clearly, there is no reason to wait."
    ),
    "localize-tone": (
        "Hey — your invoice is three weeks late. I need it paid by Friday or we stop work. "
        "Let me know."
    ),
    "continuity": (
        "Mara gazed out at the calm water with her bright blue eyes and smiled. The sea had "
        "always been her favorite place. \"Race you to the pier, Lucas!\" she called to her "
        "brother."
    ),
}
