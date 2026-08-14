# Health Adventure

## Product Specification and Incremental Implementation Plan

**Status:** Initial product specification
**Product type:** Private health, wellbeing and weight-management application
**Primary design objective:** Help a user make sustainable improvements to health and wellbeing through enjoyable, personalised daily actions rather than obsessive tracking or restriction.

---

# 1. Product vision

Health Adventure is a personalised health and wellbeing application that turns real-world healthy behaviour into an evolving journey.

Instead of functioning primarily as a calorie counter or health dashboard, the application gives the user small achievable daily goals across areas such as:

* nutrition
* physical activity
* exercise
* sleep
* mental wellbeing
* recovery
* healthy routines
* weight management

Completing real-world actions produces immediate positive feedback and contributes to longer-term progression.

Over time, the application learns:

* what the user is trying to achieve;
* which behaviours are effective;
* what the user enjoys;
* what they consistently avoid;
* what difficulty level is appropriate;
* when they are most likely to complete activities;
* how different behaviours correlate with health outcomes.

AI progressively transforms a relatively simple health tracker into a personalised adaptive coach.

The central product principle is:

> **Build a health adventure rather than a health ledger.**

---

# 2. Product principles

Every feature should satisfy these principles.

## 2.1 Behaviour first

Reward actions the user can control rather than outcomes they cannot immediately control.

Reward:

* taking a walk;
* preparing a balanced meal;
* completing a workout;
* going to bed on time;
* planning tomorrow's lunch;
* making a healthy choice after a difficult day.

Do not primarily reward:

* losing weight;
* eating as little as possible;
* achieving an ever-larger calorie deficit.

---

## 2.2 A successful day must be achievable

There should always be a small action capable of maintaining momentum.

A difficult day should not destroy weeks of progress.

The system should distinguish between:

* minimum successful day;
* good day;
* excellent day.

---

## 2.3 Never punish honest logging

Recording overeating, inactivity, poor sleep or weight gain must not cause punitive game mechanics.

The application should treat accurate information as useful data.

---

## 2.4 Recovery is part of health

Rest days, illness, holidays and disrupted routines should be expected states rather than system failures.

Recovery behaviour should itself be capable of earning progress.

---

## 2.5 Personal progress beats universal comparison

The primary competition is:

> **you now versus you before.**

Social competition should remain optional.

---

## 2.6 AI should reduce effort or improve personalisation

AI functionality should normally:

* remove logging friction;
* understand user context;
* personalise goals;
* identify useful patterns;
* provide better coaching;
* adapt difficulty.

AI should not be added merely because a conversational interface is available.

---

## 2.7 The application should eventually create independence

The long-term goal is better self-management.

The product should develop:

* skills;
* habits;
* confidence;
* understanding;
* self-efficacy.

It should not deliberately create dependence on constant app interaction.

---

# 3. Target user

Initial development should optimise for a **single-user/private application**.

This substantially simplifies:

* authentication;
* moderation;
* social systems;
* regulatory scope;
* experimentation;
* feature development.

The architecture should nevertheless avoid assumptions that make multi-user support impossible later.

---

# 4. Core health domains

The application should model health as multiple related domains.

Initial domains:

1. **Nutrition**
2. **Movement**
3. **Exercise/Fitness**
4. **Strength**
5. **Sleep**
6. **Wellbeing**
7. **Recovery**
8. **Weight/Body measurements**

Additional domains may later include:

* social wellbeing;
* medication;
* cardiovascular health;
* blood pressure;
* glucose;
* menstrual health;
* alcohol;
* smoking cessation.

The user does not have to actively work on every domain.

---

# 5. Core product loop

The primary loop is:

**Observe → Choose → Act → Record → Reward → Reflect → Adapt**

## Morning / start of day

The application proposes a small number of personalised quests.

Example:

### Today's Adventure

**Move**
Walk for 12 minutes after lunch.

**Fuel**
Include a vegetable with dinner.

**Recover**
Start winding down by 22:30.

The user can:

* accept;
* replace/reroll;
* modify;
* skip.

---

## During the day

The user completes health activities.

Activities can enter the system through:

* one-tap completion;
* manual logging;
* automated health data;
* food logging;
* conversational input;
* photographs;
* voice;
* wearable/device integrations.

Not all methods need to exist initially.

---

## Immediate reward

Completing useful behaviour generates:

* quest completion;
* XP;
* momentum;
* progress toward achievements;
* later, game-world resources.

---

## End of day

Optional lightweight reflection:

**How did today feel?**

* Good
* Okay
* Difficult

Optional:

**What helped or got in the way?**

No mandatory diary entry is required.

---

## Weekly loop

The application summarizes:

* actions completed;
* consistency;
* weight trend;
* activity;
* sleep;
* strengths;
* difficulties;
* personal records;
* emerging patterns.

The user then selects or confirms the next focus.

---

# 6. Primary navigation

Keep the application small.

## 6.1 Today

The main screen.

Contains:

* today's quests;
* daily progress;
* quick logging;
* momentum;
* current game progression;
* relevant contextual suggestion.

This should be where most interaction happens.

---

## 6.2 Journey

Longitudinal health view.

Contains:

* weight trend;
* behaviour trends;
* activity;
* sleep;
* wellbeing;
* achievements;
* milestones;
* weekly summaries.

---

## 6.3 World

Initially extremely simple.

Later contains:

* avatar;
* garden/world;
* collectables;
* upgrades;
* unlocks;
* cosmetic progression.

---

## 6.4 Coach

Contains:

* recommendations;
* insights;
* reflections;
* educational content;
* conversational AI.

This does not need to exist in the first release.

---

## 6.5 Me

Contains:

* goals;
* preferences;
* health profile;
* integrations;
* notification settings;
* application settings;
* privacy controls.

---

# 7. Minimum data model

The following conceptual entities should exist early even if their implementation is simple.

## UserProfile

* ID
* display name
* date/time zone
* height
* optional demographic data
* preferences
* onboarding state

---

## Goal

Represents an outcome or direction.

Examples:

* lose 10 kg;
* walk more;
* improve sleep;
* exercise three times weekly.

Properties:

* domain
* type
* target
* start date
* optional target date
* priority
* active/inactive

---

## Behaviour

Reusable health behaviour definition.

Examples:

* walk;
* eat fruit;
* resistance workout;
* bedtime routine.

Properties:

* domain
* description
* unit
* difficulty
* metadata

---

## Quest

Specific assigned behaviour.

Example:

> Walk for 12 minutes after lunch.

Properties:

* behaviour
* date
* target
* difficulty
* source
* status
* XP value
* optional context
* completion timestamp

Sources might be:

* manually created;
* rules engine;
* AI generated.

---

## HealthEvent

Generic recorded health behaviour or measurement.

Types include:

* weight;
* meal;
* activity;
* exercise;
* sleep;
* mood;
* measurement;
* habit;
* reflection.

Common properties:

* timestamp
* type
* source
* value/data
* confidence
* notes

---

## RewardEvent

Records game progression.

* source event
* XP awarded
* resource awarded
* achievement progress
* timestamp

This is important so the health record remains separate from the game economy.

---

## DailyState

Calculated state for a given day:

* quests;
* quests completed;
* XP;
* successful-day status;
* mood;
* momentum contribution.

---

## Achievement

* type
* requirements
* progress
* unlock state
* unlock date

---

## Insight

Later generated by rules or AI.

* text
* evidence
* relevant dates
* confidence
* category
* displayed/dismissed state

---

# 8. Game system

The game should initially be deliberately simple.

## XP

Health behaviours generate XP.

XP represents engagement in beneficial behaviour, not calories burned.

Example initial scheme:

Small action:
**10 XP**

Normal quest:
**20 XP**

Challenging quest:
**30 XP**

Weekly objective:
**50–100 XP**

Milestone:
additional bonus.

Values should remain centrally configurable.

---

# 9. Daily success

Avoid requiring all quests.

Example:

### Spark

Complete at least one meaningful healthy action.

### Good Day

Complete two health actions or reach an equivalent threshold.

### Great Day

Complete the day's broader challenge.

This gives multiple levels of success.

---

# 10. Momentum system

Do not use a brittle traditional streak as the primary metric.

Use:

> **Momentum: 18 successful days from the last 21.**

Optionally display a conventional streak as a secondary metric.

Future mechanics can include:

* grace days;
* recovery days;
* planned rest;
* holidays.

---

# 11. Achievements

Initial achievements should be behaviour-oriented.

Examples:

### Getting Started

Complete first quest.

### Moving Forward

Complete ten movement quests.

### Consistency

Have successful days on five of seven days.

### Comeback

Return after three or more inactive days.

### Explorer

Complete quests from five health domains.

### Personal Best

Beat a previous activity record.

Avoid achievements such as:

> Eat less than 1,000 calories.

---

# 12. Weight model

Weight should use a trend rather than individual values wherever possible.

Store raw measurements.

Display:

* individual readings where requested;
* moving/smoothed trend;
* weekly change;
* longer-term change.

The application should avoid excessive reaction to daily water-weight fluctuations.

Weight should be one outcome among several.

---

# 13. Nutrition model

Do not initially build a complete MyFitnessPal replacement.

Nutrition can evolve progressively.

### Initial

Track simple behaviours:

* fruit/vegetable servings;
* balanced meal;
* protein-containing meal;
* high-fibre food;
* home-cooked meal;
* water if desired.

### Later

Add:

* meal records;
* text description;
* calories/macronutrients;
* barcode database;
* photo recognition;
* AI meal interpretation.

This allows the app to be useful before a complex food database exists.

---

# 14. AI architecture

AI should be introduced in layers.

## Layer 0 — no AI

Rules generate quests.

Example:

IF movement goal active
AND yesterday's movement quest incomplete
THEN suggest easier movement quest.

This establishes deterministic application behaviour first.

---

## Layer 1 — AI text transformation

Low-risk AI tasks:

* summarize weekly activity;
* rewrite goals into friendly language;
* classify free-text reflections;
* convert natural-language logging into structured candidate data.

AI proposes data.

The user confirms important health records.

---

## Layer 2 — personalised recommendations

AI receives structured context:

* goals;
* recent quests;
* completion history;
* preferences;
* recent health events.

It proposes:

* today's quests;
* difficulty;
* alternatives;
* short explanations.

Application rules validate suggestions before presentation.

---

## Layer 3 — behavioural coaching

Conversational interface can:

* discuss barriers;
* suggest implementation intentions;
* review progress;
* help plan;
* answer relevant questions.

The LLM should have access to a structured summary of relevant user history rather than the entire raw database.

---

## Layer 4 — longitudinal intelligence

The application looks for relationships such as:

* sleep versus appetite;
* workout timing versus completion;
* weekday patterns;
* activity versus mood;
* adherence by quest type;
* effective challenge difficulty.

AI interprets statistically generated candidate findings rather than freely inventing correlations.

---

# 15. Safety architecture

Safety should exist in application logic rather than depending entirely on AI prompts.

Examples:

* minimum safe weight-loss parameters;
* limits on calorie-deficit recommendations;
* no XP proportional to calorie deficit;
* no automatic increasing exercise after overeating;
* planned rest allowed;
* ability to hide calorie data;
* ability to hide weight;
* concerning patterns can suppress certain recommendations;
* AI recommendations validated against application rules.

The app should distinguish between:

**health data**

and

**game state**.

Game mechanics should never modify historical health information.

---

# 16. Notifications

Notifications should initially be minimal.

Possible types:

* one morning quest reminder;
* one user-configured activity reminder;
* one optional evening reflection;
* weekly summary.

The user should control them individually.

Do not introduce escalating reminder frequency simply because engagement falls.

---

# 17. Implementation strategy

Development should proceed in **vertical releases**.

Every release should:

1. run;
2. preserve existing user data;
3. remain usable;
4. add one meaningful improvement to the health loop;
5. include any required database migration;
6. retain compatibility with earlier functionality.

Avoid building large unintegrated subsystems.

---

# RELEASE 0 — Product skeleton

## Objective

Establish the technical foundations while producing a navigable application.

### Implement

* application shell;
* local/private user;
* database;
* navigation;
* Today screen;
* Journey screen;
* World placeholder;
* Me/settings;
* basic reusable UI components;
* schema migrations;
* application logging;
* development/test data.

### Today screen

Initially show:

> Welcome
> Your journey starts here.

### Exit condition

Application launches reliably and persistent data survives restarts/upgrades.

---

# RELEASE 1 — First genuinely usable health app

## Objective

Create the smallest complete behaviour-change loop.

### Implement

#### Onboarding

Collect:

* primary goal;
* secondary goals;
* basic health domains;
* preferred activity level;
* relevant preferences.

#### Daily quests

Start with manually/rule-generated quests.

Support:

* display;
* complete;
* skip;
* replace.

#### XP

Award XP for completion.

#### Momentum

Calculate successful days.

#### Basic logging

Support:

* weight;
* mood;
* generic activity;
* simple habits.

#### Journey

Display:

* weight history;
* successful days;
* quest history;
* XP/level.

### Product loop now works

**Goal → Quest → Action → Log → Reward → Progress**

This is the first version worth actually using daily.

### Exit condition

Use the application personally for at least a couple of weeks without needing database edits or developer tools for ordinary operation.

---

# RELEASE 2 — Make it enjoyable

## Objective

Transform the functional tracker into a lightweight game.

### Add

* levels;
* achievements;
* daily Spark/Good/Great classifications;
* quest categories;
* quest icons;
* richer celebrations;
* personal records;
* weekly objectives;
* comeback achievement;
* collectible system;
* first simple persistent World.

The World may initially be nothing more than:

> XP causes a plant/tree/island/base to evolve visually.

Avoid complex game economies yet.

### Exit condition

Opening and completing tasks feels rewarding even without AI.

---

# RELEASE 2A — Island theme polish

## Objective

Unify the World/island scene into one coherent living picture: refresh the mascot icon and replace the generic collectible tokens with unique plants that match the island's theme.

### Implement

* fresh pass over the mascot icon (cartoon fox) — reference images to be provided by the maintainer; regenerate `static/icons/*.png` via `make_icons.py` in the same change (icons must stay token-only, R2);
* collectibles become unique island plants — one recognisable plant per collectible (or per family, per the reference set), rendered on/in the island when earned; locked tokens stay silhouettes;
* presentation-only (R10): the collectible catalogue/API contract and the engine are unchanged — no economy, XP, or progression impact;
* both themes, mobile, reduced-motion static rendering; gate and smoke pins updated with the new artwork.

### Sequencing

Rides on the merged R2 stack: the island render (`r2-world-xp-island`) and the collectibles shelf/API (`r2-completion`). Implementation starts only after the maintainer provides reference images.

### Exit condition

The World reads as one coherent living island: the mascot and every earned collectible are recognisable parts of the same scene, and no gameplay value changed.

---

# RELEASE 3 — Improve personalisation

## Objective

Make the app react intelligently without introducing LLM complexity.

### Add

Rules-based recommendation engine.

Use:

* user goals;
* past completion;
* day of week;
* recent activity;
* preferred quest types;
* difficulty history.

Implement a simple quest score:

**relevance × preference × appropriate difficulty × novelty**

Introduce:

* rerolls;
* easy mode;
* challenge mode;
* planned rest;
* recovery quests.

### Quest adaptation

Example:

Three consecutive failures
→ lower difficulty.

Repeated effortless success
→ offer harder version.

Repeated rejection
→ reduce recommendation probability.

### Exit condition

Two users with different goals/history would receive meaningfully different quest programmes.

---

# RELEASE 4 — Better tracking and automatic data

## Objective

Reduce manual entry.

### Add health-platform integration

Depending on platform:

* Android Health Connect;
* Apple HealthKit;
* wearable data where available.

Import:

* steps;
* activity;
* exercise;
* sleep;
* heart rate where useful;
* weight from connected scales where available.

### Add richer visualisations

* activity trend;
* sleep trend;
* weight trend;
* domain consistency;
* personal records.

### Add automatic quest completion where appropriate

Example:

> Walk 5,000 steps

can complete from Health Connect without user entry.

### Exit condition

Ordinary daily use requires substantially less manual logging.

---

# RELEASE 5 — First AI features

## Objective

Use AI primarily to remove friction.

### Add natural-language logging

Examples:

> "Walked the dog for about half an hour."

Proposed record:

**Walking — 30 min**

User confirms.

---

### Add free-text meal logging

> "Chicken curry, rice and peas."

Initially store description.

Later infer nutrition.

---

### Add weekly AI summaries

AI receives structured weekly metrics and produces something like:

> You were active on five days this week, your best result so far this month. Sleep was less consistent on Friday and Saturday. Your after-work walks were completed much more reliably than lunchtime ones.

The underlying metrics must be calculated by application code.

AI narrates rather than calculates critical statistics.

### Exit condition

AI demonstrably saves effort or reveals information rather than simply adding chat.

---

# RELEASE 6 — Adaptive AI coach

## Objective

Make the daily experience genuinely personalised.

### Add AI quest generation

Provide the model with:

* active goals;
* recent quests;
* completion rates;
* preferences;
* available time;
* recent health status;
* rule constraints.

Model generates candidate quests.

A deterministic validator checks:

* permitted domain;
* safe target;
* duplicate activity;
* difficulty bounds;
* contraindicated patterns where known.

Only validated quests appear.

---

### Add coaching interaction

Users can say:

> I really don't feel like exercising today.

The coach can use current context to respond:

> You've had two short nights and exercised yesterday. Would you rather make today's movement quest a ten-minute gentle walk and keep the strength session for tomorrow?

---

### Add adaptive difficulty

Use both deterministic statistics and AI reasoning.

### Exit condition

The product feels observably more personally responsive than a static health programme.

---

# RELEASE 7 — World and progression expansion

## Objective

Deepen long-term engagement.

Only do this once the health loop itself is working.

### Add

* persistent avatar;
* expanded world/garden;
* multiple upgrade paths;
* collectables;
* cosmetic unlocks;
* currencies/resources;
* discovery events;
* themed challenges;
* longer progression arcs.

Health domains can influence different parts of the world.

Example:

**Movement**
explores new territory.

**Nutrition**
grows the garden.

**Sleep**
restores energy.

**Strength**
builds structures.

**Wellbeing**
attracts characters/wildlife.

This gives otherwise abstract behaviours a visible consequence.

### Exit condition

The World provides a reason to return but does not dictate unhealthy behaviour.

---

# RELEASE 8 — Advanced intelligence

## Objective

Turn accumulated longitudinal data into useful knowledge.

### Build an analytics layer

Calculate candidate relationships.

Examples:

* average activity following different sleep durations;
* quest adherence by time;
* exercise adherence by weekday;
* mood following activity;
* weight trend versus adherence;
* meal pattern versus later hunger if captured.

Use statistical thresholds to avoid presenting meaningless noise.

### AI interprets qualified findings

Example:

> During the last eight weeks, you've completed 76% of morning exercise quests compared with 31% of evening ones.

Then:

> Shall I preferentially schedule exercise in the morning?

### Add experiments

Example:

**Two-week experiment**

> Does a ten-minute evening walk improve your sleep?

Measure before/after.

### Exit condition

The app can teach the user something useful about their own behaviour that they did not explicitly enter.

---

# RELEASE 9 — Nutrition expansion

## Objective

Only now build deeper food functionality if it remains useful.

### Add

* meal history;
* favourites;
* recipes;
* barcode lookup;
* food database;
* photo recognition;
* AI food parsing;
* macro estimates;
* energy estimates;
* meal quality indicators.

Nutrition should still support a non-calorie-focused mode.

### AI image workflow

Photo
→ AI identifies probable foods
→ proposes quantities
→ user confirms/corrects
→ nutrition record created.

Never present uncertain estimates as exact measurements.

---

# RELEASE 10 — Social features

## Objective

Add relatedness without damaging autonomy.

Because the initial application is private, this is intentionally late.

### Add

* accounts;
* friends;
* private groups;
* kudos;
* cooperative quests;
* friend streaks;
* shared challenges.

Then optionally:

* private leaderboards;
* opt-in competition.

Avoid global weight-loss leaderboards.

---

# RELEASE 11 — Maintenance and graduation

## Objective

Support health maintenance rather than endless weight loss.

When the user approaches a goal:

* reduce emphasis on weight;
* reinforce established habits;
* transition goals toward maintenance;
* reduce tracking requirements;
* progressively increase autonomy.

Potential modes:

### Active Change

Higher guidance.

### Maintenance

Lower guidance.

### Independent

Minimal tracking with occasional check-ins.

The application can re-engage when needed.

---

# 18. Recommended development order

The practical priority sequence is:

**Application skeleton**

↓

**Manual quests + basic tracking**

↓

**XP + momentum + achievements**

↓

**Rules-based personalisation**

↓

**Health integrations**

↓

**Natural-language AI logging**

↓

**AI summaries**

↓

**AI-generated adaptive quests**

↓

**AI coaching**

↓

**Rich game world**

↓

**Advanced personal analytics**

↓

**Rich nutrition**

↓

**Social systems**

This sequence deliberately introduces AI **after enough structured data exists for AI to be useful**.

---

# 19. Architecture recommendation

Use a modular monolith initially.

Avoid microservices.

Suggested logical modules:

```text
Application
│
├── Profile
├── Goals
├── Quests
├── Health Events
├── Tracking
├── Rewards
├── Progress
├── Insights
├── Integrations
├── AI
└── Notifications
```

Each should expose clear internal interfaces.

A separate AI abstraction is worthwhile from the beginning:

```text
AIService
    parseHealthEvent()
    generateSummary()
    proposeQuests()
    coach()
    explainInsight()
```

The implementation can initially return deterministic/mock responses.

Later model providers can be changed without restructuring application logic.

---

# 20. Recommended internal layering

```text
UI
↓
Application Services
↓
Domain Logic
↓
Repositories
↓
Database
```

External services sit to the side:

```text
Health Connect
AI provider
Food database
Notification service
```

Domain logic should not directly depend on a particular UI framework, LLM provider or database library.

---

# 21. Database strategy

Start with a relational database.

For a private/local implementation, SQLite is entirely reasonable.

Important requirements:

* migrations from day one;
* stable IDs;
* created/updated timestamps;
* soft deletion where historical data matters;
* raw health events remain immutable where practical;
* derived summaries can be recalculated.

Do not prematurely create a vector database.

If semantic retrieval later becomes useful, add embeddings only to relevant objects such as:

* reflections;
* coach conversations;
* insights;
* long-form notes.

Structured health data belongs in the relational database.

---

# 22. AI data flow

Do not routinely send the complete user history to an LLM.

Create a context builder:

```text
Current goals
+
Relevant preferences
+
Last 7–14 days summary
+
Recent quest performance
+
Relevant health trends
+
Specific raw events required for task
```

Then send only that context.

This makes AI:

* cheaper;
* faster;
* more reliable;
* easier to audit;
* easier to switch between providers.

---

# 23. Rules engine

Implement simple rules before AI.

Example:

```text
IF sleep < normal
AND yesterday contained strenuous exercise
THEN reduce probability of high-intensity quest
```

```text
IF movement quests completed < 40% over last 7 attempts
THEN reduce movement quest difficulty
```

```text
IF user rejects a quest category 3 times
THEN reduce its recommendation weighting
```

```text
IF user is returning after inactivity
THEN generate Recovery/Restart programme
```

AI can later reason around these rules but should not silently override safety constraints.

---

# 24. Recommendation engine evolution

## Version 1

Random selection from appropriate quest templates.

## Version 2

Weighted templates based on goals.

## Version 3

Weighted by historical adherence.

## Version 4

Context-sensitive rules.

## Version 5

AI proposes candidate quests.

## Version 6

Hybrid recommender learns which quests produce sustainable completion and health improvement.

This gradual progression makes the recommendation system testable at every stage.

---

# 25. Telemetry worth collecting from the beginning

Even in a private app, store product interaction data locally.

Examples:

* quest presented;
* quest accepted;
* quest rerolled;
* quest completed;
* quest skipped;
* completion latency;
* screen opened;
* feature used;
* notification acted on.

This allows questions such as:

> Which quest types get completed?

> Does rerolling increase completion?

> Does the game world increase usage?

> Do users actually read AI summaries?

For a private app this can remain entirely local.

---

# 26. Core product metrics

Do not optimise only for screen time.

Primary health/product metrics should eventually include:

### Behaviour

* successful days/week;
* quest completion rate;
* active days;
* adherence by domain;
* recovery following lapse.

### Retention

* D1;
* D7;
* D30;
* weekly active use.

### Health

* weight trend where appropriate;
* activity;
* sleep;
* fitness;
* domain-specific goals.

### User autonomy

A particularly useful long-term metric:

> **Can the user maintain healthy behaviours with fewer prompts?**

---

# 27. Feature flags

Use feature flags early.

Examples:

```text
ai_logging
ai_quests
world_enabled
nutrition_tracking
weekly_summary
health_connect
adaptive_difficulty
```

This makes incremental development significantly easier.

Experimental functionality can be enabled without maintaining separate application branches.

---

# 28. Testing priorities

## Domain tests

Highest priority.

Test:

* XP calculations;
* momentum;
* quest completion;
* goal progression;
* weight trends;
* recommendation rules;
* safety constraints.

---

## Integration tests

Test:

* persistence;
* health data imports;
* migrations;
* AI structured outputs.

---

## AI tests

Maintain fixed scenarios.

Example:

**User**

* wants weight loss;
* slept four hours;
* completed intense workout yesterday.

The system should not generate:

> Run 10 km today.

AI outputs should be validated programmatically.

---

# 29. Suggested initial technical milestones

## Milestone A

Working app + persistence.

## Milestone B

Manual health tracker.

## Milestone C

Daily quests.

## Milestone D

Rewards and momentum.

At this point:

> **Start using the application daily.**

Everything afterwards should be guided partly by actual friction discovered through use.

## Milestone E

Personalised rules.

## Milestone F

Automatic health data.

## Milestone G

AI logging.

## Milestone H

AI recommendations.

## Milestone I

Game-world expansion.

---

# 30. What NOT to build initially

Explicitly defer:

* full calorie database;
* complex AI agent system;
* social network;
* multiplayer;
* huge avatar system;
* recipes;
* coaching marketplace;
* dozens of charts;
* subscription/billing;
* complex cloud infrastructure;
* custom machine-learning models;
* vector databases;
* elaborate notification engine;
* massive educational content library.

All are attractive distractions before the core loop is validated.

---

# 31. First usable version

The first version worth aiming for should therefore contain only:

### Today

* three quests;
* completion buttons;
* quick log;
* daily XP;
* momentum.

### Journey

* weight trend;
* activity history;
* quest completion;
* level;
* achievements.

### World

* one simple object that evolves with XP.

### Me

* goals;
* priorities;
* preferences.

### System

* local persistence;
* migrations;
* rules-based quest generation.

That is enough to validate the central hypothesis:

> **Does turning small personalised health behaviours into a visible daily adventure make the user want to continue improving?**

---

# 32. Definition of success for each release

Every development iteration should satisfy four conditions:

### 1. It works

No knowingly broken user journey.

### 2. Existing data survives

Schema changes migrate cleanly.

### 3. The product remains usable

A partially implemented future feature must not interfere with normal use.

### 4. It improves one of three things

A feature must meaningfully improve at least one of:

**Health effectiveness**

Does it help the user act more healthily?

**Engagement**

Does it make healthy behaviour more enjoyable or sustainable?

**Friction**

Does it make the same useful behaviour easier?

If it does none of these, it should probably not be built.

---

# 33. Overall product evolution

The intended evolution is:

### Stage 1 — Useful

> "This helps me organise my health goals."

### Stage 2 — Engaging

> "I actually want to complete today's quests."

### Stage 3 — Personal

> "It understands what works for me."

### Stage 4 — Intelligent

> "It notices patterns I hadn't realised."

### Stage 5 — Habit-forming

> "These behaviours are becoming normal."

### Stage 6 — Empowering

> "I know how to manage this myself."

That should remain the long-term product trajectory.

