"""Independent timetable search over the same terms; run with --write to refresh expected.out."""
from pathlib import Path
import sys

HERE = Path(__file__).parent


def read_terms(text):
    terms = []
    for raw in text.split('\n'):
        words = raw.split()
        if not words or words[0].startswith('#'):
            continue
        if words[0] == 'term' and len(words) == 2:
            terms.append(dict(name=words[1], rooms=[], periods=[], away={}, courses=[], enrolled={}))
            continue
        term = terms[-1]
        kind = words[0]
        if kind == 'room':
            term['rooms'].append((words[1], int(words[2]), len(words) > 3 and words[3] == 'lab'))
        elif kind == 'periods':
            term['periods'].extend(words[1:])
        elif kind == 'away':
            term['away'][words[1]] = words[2:]
        elif kind == 'course':
            term['courses'].append((words[1], words[2], int(words[3]), len(words) > 4 and words[4] == 'lab'))
        elif kind == 'enroll':
            term['enrolled'][words[1]] = words[2:]
    return terms


def choices(term, course):
    name, teacher, size, lab = course
    away = term['away'].get(teacher, [])
    rooms = sorted(range(len(term['rooms'])), key=lambda r: term['rooms'][r][1])
    out = []
    for p, period in enumerate(term['periods']):
        if period in away:
            continue
        for r in rooms:
            _, capacity, is_lab = term['rooms'][r]
            if capacity >= size and is_lab == lab:
                out.append((p, r))
    return out


def clashes(term):
    courses = term['courses']
    table = [[False] * len(courses) for _ in courses]
    for i, a in enumerate(courses):
        for j, b in enumerate(courses):
            if i != j and (a[1] == b[1] or any(a[0] in names and b[0] in names for names in term['enrolled'].values())):
                table[i][j] = True
    return table


class Stats:
    tried = 0
    backtracks = 0


def solve(stats, options, placed, clash):
    best = None
    for i, choices_left in enumerate(options):
        if i in placed:
            continue
        if best is None or len(choices_left) < len(options[best]):
            best = i
    if best is None:
        return placed
    for pick in options[best]:
        stats.tried += 1
        narrowed, dead = [], False
        for other, choices_left in enumerate(options):
            if other == best or other in placed:
                narrowed.append(choices_left)
                continue
            kept = [c for c in choices_left if c[0] != pick[0] or (c[1] != pick[1] and not clash[best][other])]
            if not kept:
                dead = True
                break
            narrowed.append(kept)
        if dead:
            stats.backtracks += 1
            continue
        done = solve(stats, narrowed, {**placed, best: pick}, clash)
        if done is None:
            stats.backtracks += 1
            continue
        return done
    return None


def report(term, out):
    courses, rooms, periods = term['courses'], term['rooms'], term['periods']
    out.append(f"term {term['name']}: {len(courses)} courses, {len(rooms)} rooms, {len(periods)} periods, {len(term['enrolled'])} students")
    options = [choices(term, c) for c in courses]
    for c, o in zip(courses, options):
        if not o:
            out.append(f'  no timetable: {c[0]} has no room and period it could use')
            return
    stats = Stats()
    placed = solve(stats, options, {}, clashes(term))
    if placed is None:
        out.append(f'  no timetable after {stats.tried} assignments')
        return
    out.append(f'  timetable after {stats.tried} assignments, {stats.backtracks} undone:')
    width = max([8] + [len(c[0]) + 2 for c in courses])
    out.append(('  ' + 'period'.ljust(8) + ''.join(r[0].ljust(width) for r in rooms)).rstrip())
    for p, period in enumerate(periods):
        line = '  ' + period.ljust(8)
        for r in range(len(rooms)):
            cell = '-'
            for i, c in enumerate(courses):
                if placed.get(i) == (p, r):
                    cell = c[0]
            line += cell.ljust(width)
        out.append(line.rstrip())
    teachers = []
    for c in courses:
        if c[1] not in teachers:
            teachers.append(c[1])
    for t in teachers:
        slots = [f'{c[0]} {periods[placed[i][0]]} {rooms[placed[i][1]][0]}' for i, c in enumerate(courses) if c[1] == t]
        out.append(f"  {t}: {', '.join(slots)}")


def run():
    out = []
    for term in read_terms((HERE / 'stdin.txt').read_text()):
        report(term, out)
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    expected = HERE / 'expected.out'
    if sys.argv[1:] == ['--write']:
        expected.write_text(run())
    elif sys.argv[1:] == ['--show']:
        print(run(), end='')
    elif expected.read_text() != run():
        sys.exit('expected.out differs from the timetable search')
