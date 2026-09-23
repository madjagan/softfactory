# Why do we need testing?

The goal of testing is to **find bugs and assess the quality of the software we deliver**.

A bug is software behaving in a way that you do not expect. To recognise a bug, you first need to understand the **expected behaviour**.

To understand expected behaviour, understand:
- Who uses the software?
- Why do they use it? What are their goals?
- How do they use the software to achieve those goals?

This understanding forms the foundation of our testing.

## Start with a test plan

Based on our understanding of users, goals, and workflows, we create a **test plan**.

The test plan identifies the important functionality and scenarios that we need to verify. It provides **broad direction** rather than attempting to describe every possible test.

In today's AI-assisted development environment, we can generate and automate many structured tests. This allows us to systematically verify what we already know we need to test.

But the test plan is **not a boundary**.

## Explore beyond the plan

A test plan represents what we currently know we should test. It cannot capture everything that can go wrong.

Bugs can exist because:

- We misunderstood how users would use the software.
- We did not anticipate certain inputs or combinations of actions.
- Users follow workflows we did not consider.
- Different features interact in unexpected ways.
- Real-world data differs from our test data.
- A change in one area creates unexpected behaviour elsewhere.

This is where **human exploratory testing** becomes important.

Start with the test plan as your guide. Then explore.

Try variations of the planned scenarios. Change the inputs. Change the sequence of actions. Skip steps. Repeat actions. Combine features. Try unusual but plausible user behaviour.

Ask yourself:

- What else might the user do here?
- What happens if I do this differently?
- What happens if my assumptions are wrong?
- What have we not thought about?

**The test plan gives you direction. Exploration gives you discovery.**

## Learn from what you discover

When exploration uncovers something that was not in the test plan, investigate it.

If you find a bug, report:

- **Issue description:** What is the problem?
- **Current behaviour:** What does the software actually do?
- **Expected behaviour:** What should it do?

Report it through the bug-reporting system. The bug is then root-caused, fixed, and reverified.

But do not stop there.

Ask what we can learn from the bug. Should we add a new test? Should we add a new category of testing? Should we change our understanding of expected behaviour?

Feed these learnings back into the test plan and automated test generation.

This creates a continuous learning loop:

**Plan → Test → Explore → Discover → Fix → Learn → Improve the tests**

## The mindset

**Do not just execute tests. Explore the software.**
Automation is excellent at systematically checking what we know.
Human exploration helps us discover **what we did not know we needed to check**.
That discovery is a critical part of improving software quality.
