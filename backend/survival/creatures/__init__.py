"""Creatures: the animals that share Mimo's world (Living World L1).

The server owns them, like Mimo: they live in the world database (backend.survival.creatures.table)
and move inside the tick (backend.survival.creatures.simulate), and the viewer only draws them.
- kinds: what each kind of creature is, as plain data in a registry.
- table: the creatures and creature_chunks tables, and `Herd`, how the tick and readers reach them.
- moves: greedy one-block moves by the Grid's rules, seeded rolls and where a creature is now.
- acts: the creature-action registry (flee, swim, graze, wander, idle) and the Scene they act in.
- spawning: herds that appear the first time Mimo comes near a chunk, the caps, and animals coming back.
- simulate: the creature hook advance_world calls after each chunk of Mimo's actions.
- combat: the generic attack step and what a blow does to any creature.
- hunting: the hunt purpose.
- fishing: fish in the water show where a catch comes from.
- view: what /api/mimo streams about them.
This module imports nothing, so any of them can be imported on its own without a cycle.
"""
