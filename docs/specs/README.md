# Smartly Architecture Specs

本資料夾存放 Smartly Bridge 未來目標架構的規格文件。

這些文件描述的是「規劃中的穩定架構」，不以目前程式碼實作為準，也不以單一現有裝置為設計中心。後續現有版本應逐步往這些 spec 收斂。

## Relationship To Master Plan

[smartly_bridge_architecture_plan.md](../smartly_bridge_architecture_plan.md) 是總入口，負責描述整體架構、分層、roadmap 與 spec 索引。

本資料夾內的文件是可被 Bridge、Platform、adapter、測試與文件實作依賴的正式子規格。當總計畫與子規格衝突時，應先修正總計畫的索引與摘要，並以對應子規格作為實作細節的 source of truth。

## Spec Index

| Spec | Purpose | Status |
|---|---|---|
| [Device Abstraction](device-abstraction.md) | 定義 logical device、capability、adapter、presentation、command/state/event 的長期架構合約 | Draft |
| [Capability Contracts](capability-contracts.md) | 定義 capability state、command、event、constraints、unit、錯誤行為與擴充規則 | Draft |
| [Adapter Contract](adapter-contract.md) | 定義 adapter manifest、match、normalize、execute、event、health、sandbox 與測試要求 | Draft |
| [Presentation Contract](presentation-contract.md) | 定義 Platform 如何以 primary type、capability 與 presentation hint render UI | Draft |
| [API vNext Contract](api-vnext-contract.md) | 定義 logical device sync、state sync、event ingestion、command dispatch 與 diagnostic fetch | Draft |
| [Migration Plan](migration-plan.md) | 定義從 entity-based 架構遷移到 logical-device / capability-based 架構的階段與 gate | Draft |
| [Phase 6 Release Evidence](phase6-release-evidence.md) | 紀錄 Phase 6 API vNext cleanup release gates 的外部證據、owner、判定與 sign-off | Active |
| [Migration Progress](migration-progress.md) | 紀錄 `dev` 上已完成的遷移 slices、測試證據與待辦項目 | Active |
