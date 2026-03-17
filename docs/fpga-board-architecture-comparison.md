# FPGA Board-Architecture Comparison

> A board-architecture-focused comparison of the currently validated FPGA families in `opendatasheet`: AMD Artix/Kintex UltraScale+, Intel/Altera Agilex 5, Lattice ECP5/CrossLink-NX, and Gowin Arora V.

## Scope

This document is written from the viewpoint of a **board architect / schematic owner**, not a pure RTL engineer and not a marketing comparison.

The goal is not to answer "which FPGA is strongest", but:

- which vendor/family fits a given system role,
- what board-level cost comes with that choice,
- where the real risk moves after the device is selected,
- what should be frozen at architecture review rather than left to schematic or layout.

This comparison is intentionally anchored to the families currently covered and validated in this repository:

- **AMD**: Artix UltraScale+, Kintex UltraScale+
- **Intel/Altera**: Agilex 5
- **Lattice**: ECP5, CrossLink-NX
- **Gowin**: Arora V

It is therefore not a universal statement about each vendor's entire product line. It is a board-architecture reading of the families we already parse, export, and test.

## Executive Summary

If the same functional requirement is implemented on these four vendors, the biggest difference is usually **not** LUT count or DSP count. The biggest difference is the amount and shape of **system coupling** introduced into:

- power rails,
- bank planning,
- clock topology,
- boot and recovery path,
- high-speed routing,
- memory interface strategy,
- bring-up observability,
- toolchain and document discipline.

At a high level:

- **AMD** is strongest when the FPGA is the **system center** and the team is willing to accept heavy board-level discipline.
- **Intel/Altera** is strongest when the FPGA is really a **platform node** with SoC-like responsibilities, especially when HPS, DDR, and high-speed I/O are part of the same system decision.
- **Lattice** is strongest when the architectural goal is to **keep the board simple** and isolate the FPGA as a focused feature block rather than make it the center of gravity.
- **Gowin** is strongest when cost, availability, or domestic-supply-chain constraints matter, **provided** the team explicitly budgets for higher verification effort and more defensive board design.

The real architectural question is not "who wins". It is:

> Which FPGA family introduces the least damaging system-level coupling for the role this board actually needs?

## What A Board Architect Actually Optimizes

Board architects are usually not solving a single-chip optimization problem. They are solving a **system survivability** problem.

The most important evaluation axes are:

1. **Power topology complexity**
   More rails, tighter windows, stricter sequencing, and higher transient current all directly increase board risk.

2. **Bank planning rigidity**
   If interfaces cannot move freely across banks, then package selection becomes architecture, not implementation.

3. **Boot and recovery path**
   Configuration source, rescue path, production programming, field update, and failure recovery all need to be designed before schematic completion.

4. **Clock-tree ownership**
   The FPGA may be a clock consumer, a clock distributor, or the root of a protocol timing domain. Those are radically different board responsibilities.

5. **Physical realizability of high-speed links**
   "Supports PCIe" is meaningless unless the chosen package, lane group, refclk topology, and connector escape are all compatible.

6. **Memory-interface cost**
   DDR and LPDDR are not just controller features. They are board topology commitments involving specific banks, specific packages, and often irreversible routing choices.

7. **Bring-up observability**
   JTAG, status pins, power-good chain, reset segmentation, refclk visibility, and test points are not optional luxuries on FPGA boards.

8. **Document and toolchain coherence**
   Architecture mistakes often come from mixing family-level marketing statements with package-level facts. The board architect must police that boundary.

Viewed through those eight axes, the four vendor families behave very differently.

## AMD: Best When The FPGA Is The System Center

For the currently validated UltraScale+ families in this repository, AMD behaves like a vendor that assumes the board team is willing to adopt the FPGA's internal organization as a board-design constraint.

That is not a criticism. It is the reason AMD works very well for high-performance systems.

### Board-Level Character

AMD devices in this class push the architect toward:

- early bank floorplanning,
- strong separation of I/O bank roles,
- explicit GT/refclk topology decisions,
- more disciplined power design,
- tighter coupling between package choice and external interface map.

The board does not "contain an FPGA". The board is often **organized around the FPGA**.

### Strength

AMD is especially strong when:

- the FPGA owns the data plane,
- multiple high-speed protocols must coexist,
- the design needs serious transceiver planning,
- the board can justify heavy early package and pin planning,
- the team already has mature PI/SI and bring-up practices.

In that environment, AMD's stricter organization becomes an advantage. Rules are heavy, but they are legible.

### Cost

The cost is not just device price. The cost is:

- more architectural work before schematic entry,
- more fragile late-stage interface changes,
- higher sensitivity to bank and package mistakes,
- higher risk of turning the FPGA into an over-centralized system dependency.

This last point matters. Many AMD boards do not fail because the chip is too small. They fail because too many system responsibilities migrate into the FPGA simply because it can handle them.

### Architect's Failure Mode

The typical AMD architecture failure is:

> selecting a powerful FPGA first, then allowing the whole board to orbit around it until every late change becomes painful.

### Best Fit

- high-speed acquisition boards,
- protocol concentrators,
- accelerator cards,
- transceiver-heavy communication or instrumentation systems,
- systems where the FPGA really is the primary system engine.

### Poor Fit

- simple bridge/control boards,
- projects where schedule is tighter than performance,
- teams that want to defer interface freeze until late schematic/layout phases.

## Intel/Altera: Best When The FPGA Is A Platform Node

For Agilex 5, the main architectural distinction is that the device behaves less like a standalone logic island and more like a **platform component**.

This is especially true when HPS, EMIF, transceivers, and system-management functions all enter the same decision space.

### Board-Level Character

Intel/Altera in this class encourages platform-style thinking:

- the FPGA may be part logic fabric, part control plane, part SoC,
- package-level reality must be read separately from family-level capability,
- ordering variant matters,
- HPS/EMIF assumptions affect board partitioning much earlier,
- boot and software-bring-up decisions are tied more tightly to hardware architecture.

For a board architect, this means the device cannot be selected in isolation. It must be selected together with:

- boot chain,
- external memory plan,
- software strategy,
- debug path,
- package variant assumptions,
- board partitioning between control and data planes.

### Strength

Intel/Altera is particularly attractive when:

- the board wants a strong control-plane + data-plane combination,
- external CPU count should be reduced,
- HPS is valuable,
- memory and system-management roles need to be concentrated,
- the design is intentionally a platform board rather than a single-purpose logic board.

### Cost

The main cost is architectural rigidity.

A board team must separate at least four layers of truth:

1. **family-level summary**
2. **device-level capability boundary**
3. **ordering-variant role/features**
4. **package-level pin/package facts**

The most dangerous mistake is to treat device-overview capability as package-level board permission. That leads to classic late-stage surprises:

- the package does not expose the needed lane group,
- the chosen variant does not include the expected hard function,
- HPS/EMIF has already consumed the wrong bank region,
- the protocol is family-supported but not board-realizable on the selected package.

### Architect's Failure Mode

The typical Intel/Altera architecture failure is:

> using family or device capability material as if it were enough to commit board topology, without proving package- and variant-level realizability.

### Best Fit

- platform boards,
- edge compute/control systems,
- FPGA + software co-designed systems,
- boards where HPS and FPGA fabric are intentionally part of one system node.

### Poor Fit

- simple programmable-logic insertions,
- projects whose system partition is still unstable,
- teams that do not want SoC-class bring-up complexity.

## Lattice: Best When The Board Should Stay Simple

Among the families currently covered in this repository, Lattice is the easiest to map to the philosophy:

> solve the board problem without turning the FPGA into the whole board.

That is the core appeal.

### Board-Level Character

ECP5 and CrossLink-NX usually fit architectures where the FPGA is:

- an interface bridge,
- a focused datapath block,
- a display/camera interconnect node,
- an always-on helper,
- a moderate-complexity programmable block at the system edge.

The rest of the board does not have to re-center itself around the FPGA.

### Strength

For the board architect, Lattice often buys:

- fewer system-level commitments,
- lighter power-tree stress,
- easier bring-up isolation,
- lower risk of centralizing too many responsibilities in one device,
- a cleaner partition between main processor and programmable edge logic.

This is particularly valuable in products where:

- the real need is bridge logic,
- I/O transformation matters more than raw dataplane scale,
- power and schedule matter more than peak performance,
- a smaller system is an explicit architectural goal.

### Cost

The cost is that the ceiling arrives sooner.

Lattice is usually a very good answer only while the architect maintains discipline about scope. Once the project quietly becomes:

- a transceiver-heavy platform,
- a memory-heavy compute board,
- or a board with expanding protocol ambitions,

then Lattice stops reducing complexity and starts becoming the wrong tool.

### Architect's Failure Mode

The typical Lattice architecture failure is:

> forcing a small-system FPGA to serve as a disguised platform FPGA after the requirements have already outgrown it.

### Best Fit

- camera/display bridge boards,
- low-power edge logic,
- moderate-speed protocol adaptation,
- helper/control FPGAs,
- architectures where the FPGA should remain a bounded subsystem.

### Poor Fit

- transceiver-heavy platform boards,
- designs likely to grow into broad high-speed dataplanes,
- projects where memory, control, and acceleration all need to collapse into one programmable center.

## Gowin: Best When Cost/Availability Matter And Verification Is Treated As A First-Class Budget Item

Gowin is often misread as either "cheap FPGA" or "domestic substitution". From a board architect's viewpoint, neither description is sufficient.

The more accurate statement is:

> Gowin is a viable architectural choice when commercial constraints are real, but the resulting uncertainty must be actively engineered around.

### Board-Level Character

In the Arora V class currently covered here, Gowin can be architecturally useful for:

- moderate-complexity industrial boards,
- custom interface concentration,
- cost-sensitive programmable logic,
- systems where local supply-chain considerations matter,
- designs willing to spend more effort on practical board validation.

### Strength

The attraction is not only unit price. It is a package of:

- acceptable capability for many midrange boards,
- potentially favorable commercial positioning,
- domestic-source relevance for some programs,
- enough programmability to eliminate fixed-function glue.

### Cost

The hidden cost is engineering uncertainty.

That uncertainty appears in four places:

1. **document-boundary effort**
   The team must be more careful about deciding which document is family summary, device boundary, package fact, devkit reference, or design guidance.

2. **toolchain learning cost**
   Even if the silicon is good enough, the team must budget for flow familiarity and corner-case validation.

3. **defensive board design**
   A Gowin architecture benefits from more intentional fallback features:
   - retained JTAG,
   - alternate clock options,
   - flexible boot path,
   - extra bring-up observability,
   - cleaner isolation of uncertain interfaces.

4. **organizational fit**
   Teams that are disciplined and pragmatic can absorb the added validation burden. Teams relying heavily on vendor-process maturity may struggle more.

### Architect's Failure Mode

The typical Gowin architecture failure is:

> assuming cost savings at the device level automatically translate into system savings, while ignoring additional verification and bring-up cost.

### Best Fit

- cost-sensitive industrial and interface boards,
- moderate complexity systems,
- teams willing to invest in explicit board-level validation,
- projects where availability or domestic-supply constraints are real drivers.

### Poor Fit

- schedule-critical projects with little validation margin,
- transceiver-heavy or platform-heavy designs,
- teams that cannot afford document/tooling gray-zone overhead.

## Comparative Matrix For Architecture Review

| Dimension | AMD | Intel/Altera | Lattice | Gowin |
|---|---|---|---|---|
| Current covered families | Artix U+, Kintex U+ | Agilex 5 | ECP5, CrossLink-NX | Arora V |
| System role fit | System center | Platform node | Edge feature block | Flexible, but verification-heavy |
| Board-level complexity | High | High to very high | Low to medium | Medium |
| Power-discipline burden | High | Very high | Medium | Medium |
| Bank-planning rigidity | Strong | Strong | Medium | Medium to strong |
| Boot-path complexity | Medium to high | High | Low to medium | Medium |
| High-speed physical coupling | High | High | Medium/limited | Moderate, family dependent |
| DDR / memory-system coupling | High | Very high | Low to medium | Medium |
| Bring-up observability demand | Must be designed in | Must be designed in | More forgiving | Needs defensive design |
| Tool/document discipline burden | High but structured | High and layered | Moderate | Must be actively managed |
| Common overreach pattern | FPGA becomes too central | Platform assumptions committed too early | Device ceiling exceeded late | Validation burden underestimated |

## How To Use This Matrix

The right reading is not "higher complexity is bad". The right reading is:

- does the board **need** that complexity,
- can the team **absorb** that complexity,
- and does the schedule **allow** that complexity.

For example:

- If the board is a high-speed acquisition or accelerator card, AMD's complexity may be exactly justified.
- If the board is a platform node combining software control, memory, and programmable acceleration, Intel/Altera may be the cleanest answer.
- If the board should remain decomposable and low-risk, Lattice is often the most architecturally disciplined choice.
- If cost and availability are hard constraints, Gowin may be the right answer only if the team explicitly funds the extra validation effort.

## Architecture Selection Checklist

Use this checklist before final device/package commitment.

### 1. System Role

- Is the FPGA a system center or an edge feature block?
- If the FPGA does not configure, can the rest of the board still partially boot for diagnosis?
- Is the FPGA being asked to solve an actual requirement, or absorb scope creep?

### 2. I/O And Bank Planning

- Has each external interface been assigned to a specific bank region?
- Are all bank voltage assumptions already frozen?
- Are package-level facts confirmed, not inferred from family-level documents?
- Is package migration genuinely possible, or only nominally possible?

### 3. Power Architecture

- Are all mandatory rails enumerated, including auxiliary and transceiver-related rails?
- Are sequencing assumptions proven, not guessed?
- Is there a realistic transient-current and decoupling plan?
- Can power faults be diagnosed from board observability?

### 4. Boot And Recovery

- What is the primary boot source?
- What is the minimum rescue path if the primary boot path fails?
- Can production programming, lab bring-up, and field recovery all be supported by the same board?
- Is reset segmented enough to isolate FPGA bring-up from full-board reset?

### 5. Clocking

- Who owns the board's root clocks?
- Which clocks are protocol-quality refclks versus general management clocks?
- Are protocol and fabric clock responsibilities being mixed in a dangerous way?
- Can the board isolate jitter-path failures?

### 6. High-Speed Interfaces

- Are the lane groups physically realizable on the chosen package?
- Are the refclk sources aligned to those lane groups?
- Does connector pinout increase escape cost beyond budget?
- Is there a physical-layer debug plan if the link does not train?

### 7. Memory Interfaces

- Is the exact memory topology frozen to package and bank?
- Does the board depend on DDR/LPDDR working before meaningful debug can begin?
- Has routing freedom been budgeted realistically?

### 8. Bring-Up And Observability

- Is JTAG retained?
- Are configuration and error-status signals visible?
- Are key rails and clocks measurable?
- Is there enough instrumentation to tell power, boot, and clock failures apart?

### 9. Team And Delivery Fit

- Does the team actually have experience matching the chosen device class?
- Is toolchain maturity for this team sufficient for production, not just demo?
- Is the delivery schedule compatible with the expected first-board learning curve?

## Typical Project-Type Recommendations

### High-Speed Acquisition / Interconnect / Acceleration Board

- **Prefer**: AMD
- **Second look**: Intel/Altera
- Reason: these boards usually justify strong transceiver planning and FPGA-centric architecture.

### SoC + FPGA Platform Board

- **Prefer**: Intel/Altera
- **Second look**: AMD
- Reason: when control plane, memory, and programmable acceleration are intentionally co-designed, platform-style integration matters more.

### Bridge / Display / Camera / Always-On Helper Board

- **Prefer**: Lattice
- **Second look**: Gowin
- Reason: the board usually benefits from keeping the FPGA bounded, low-power, and peripheral to the main system.

### Cost-Sensitive Industrial Control / Custom Interface Board

- **Prefer**: Gowin
- **Second look**: Lattice
- Reason: cost and availability matter, but only if validation burden is accepted up front.

## Review Templates

These templates are intended for architecture review meetings.

### Template A: Positive Recommendation

> Recommend `vendor + family + device/package` because its **board-level coupling profile** matches the actual system role.  
> The decision is driven less by logic-resource headline numbers and more by:  
> `power topology fit / bank realizability / package-level interface mapping / boot path / bring-up observability`.  
> This choice is valid provided the following assumptions remain frozen:  
> `list 2-4 assumptions`.

### Template B: Negative Recommendation

> Do not recommend `vendor + family` for this board.  
> The device is capable, but the board-level cost is mismatched to the actual project need.  
> It would add unnecessary complexity in:  
> `power / clocking / bank planning / boot / toolchain / verification`.  
> This is therefore a technically possible but architecturally inefficient option.

### Template C: Conditional Recommendation

> `vendor + family` is acceptable only if the project freezes the following before schematic completion:  
> `package selection / bank map / boot path / DDR plan / refclk ownership`.  
> If those items remain unstable, the architecture risk is higher than the benefit of the device.

## Three High-Value Questions For Any FPGA Review

1. **Is this FPGA solving a system problem, or creating a larger system around itself?**
2. **Are we buying logic capacity, or buying a board-level burden in power, clocks, boot, and debug?**
3. **If this FPGA takes two extra months to bring up, is the overall project still healthy?**

## Final Recommendation Pattern

The shortest useful vendor-selection rule from a board architect's viewpoint is:

- Choose **AMD** when the FPGA truly is the high-speed system center.
- Choose **Intel/Altera** when the FPGA is really a platform node with SoC-like responsibility.
- Choose **Lattice** when the board should stay decomposable and low-complexity.
- Choose **Gowin** when cost/availability matter enough to justify a larger validation budget.

That framing is usually more valuable than a raw LUT/DSP/SerDes comparison, because boards do not fail on marketing tables. They fail where architecture leaves hidden coupling unmanaged.
