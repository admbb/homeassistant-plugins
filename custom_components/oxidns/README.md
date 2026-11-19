# OxiDNS Home Assistant 集成

此集成通过 OxiDNS 管理 API 只读采集健康状态、所选指标采集器的计数和速率、查询记录器的采样统计，并可监听实时查询事件。OxiDNS 服务项目：[svenshi/oxidns](https://github.com/svenshi/oxidns)。

将 `custom_components/oxidns` 复制到 Home Assistant 配置目录的 `custom_components` 下，重启 Home Assistant 后，从“设置 → 设备与服务 → 添加集成”搜索 OxiDNS。按实际配置填写地址、端口和凭据；默认端口为 9199。同类插件只有一个且配置接口可读取时，会自动选择查询记录器和指标采集器标签，否则需要手动填写。

实时查询实体默认禁用。启用后，查询域名和客户端地址可能被 Home Assistant 记录；`oxidns_query_received` 事件也包含这些信息。断线期间的实时事件不会自动补发。统计数据来自最近一小时的查询记录样本，数据量超过服务端限制时可能被截断；有关样本数量和截断的信息位于实体属性中。

集成原始实现和许可来自本地 `home-assistant-oxidns` 项目；许可证见本目录 [LICENSE](LICENSE)。
