const TOKEN_STORAGE_KEY = "dedicated_line_token";
const QUERY_PARAMS = new URLSearchParams(window.location.search);
const PREVIEW_MODE = QUERY_PARAMS.get("preview") === "1";
const PREVIEW_INITIAL_MODULE = QUERY_PARAMS.get("module") || "";
const PREVIEW_LINE_SOURCE_TYPE = QUERY_PARAMS.get("source_type") || "";
const PREVIEW_ONU_SERVICE_TYPE = QUERY_PARAMS.get("service_type") || "";

const previewUser = {
  id: 1,
  username: "admin",
  display_name: "系统管理员",
  roles: ["admin"],
  permissions: ["data.query", "data.export", "user.manage"],
};

// Fictional preview fixtures; never loaded from a deployment database.
const previewData = {
  "lineItems": [
    {
      "id": 12031,
      "source_type": "互联网专线",
      "area": "示例区1",
      "customer_name": "示例企业1（虚构）",
      "product_number": "DEMO-1",
      "product_type": "商务互联网专线",
      "access_method": "PON接入",
      "bandwidth": "100",
      "order_no": "DEMO-1",
      "assurance_level": "标准",
      "olt_port_name": "DEMO-1",
      "splitter_name": "DEMO-1",
      "user_address": "192.0.2.11",
      "gateway_address": "192.0.2.11",
      "service_status": "正使用",
      "open_time": "2026-01-01 10:00:00",
      "line_name": "DEMO-1",
      "raw_data": {
        "区域": "示例区1",
        "核查状态": "DEMO-1",
        "核查信息": "DEMO-1",
        "是否拓扑完整": "DEMO-1",
        "产品号码": "DEMO-1",
        "调度中产品号码": "DEMO-1",
        "产品实例编码": "DEMO-1",
        "产品类型编码": "DEMO-1",
        "产品类型": "商务互联网专线",
        "子产品类型": "DEMO-1",
        "工单类型": "DEMO-1",
        "服开工单号": "DEMO-1",
        "业务所属地市": "示例市",
        "业务相关地市": "示例市",
        "业务状态": "正使用",
        "开通日期": "2026-01-01 10:00:00",
        "客户集团编码": "DEMO-1",
        "客户名称": "示例企业1（虚构）",
        "客户所属地市": "示例市",
        "客户类型": "DEMO-1",
        "专线名称": "DEMO-1",
        "光路名称": "DEMO-1",
        "传输电路名称": "DEMO-1",
        "网管电路名称": "DEMO-1",
        "业务带宽": "100",
        "上行带宽": "100",
        "楼宇编码": "DEMO-1",
        "楼宇名称": "DEMO-1",
        "流程中业务状态": "DEMO-1",
        "业务用途描述": "DEMO-1",
        "客户配合联系人": "DEMO-1",
        "客户配合联系人电话": "DEMO-PHONE",
        "数据来源": "DEMO-1",
        "来源类型": "互联网专线",
        "业务保障等级": "DEMO-1",
        "验收交维状态": "DEMO-1",
        "客户机房地址": "DEMO-1",
        "故障修复时限签约承诺": "DEMO-1",
        "第三方出口方式": "DEMO-1",
        "登录帐号": "DEMO-1",
        "是否接入省级加速平台": "DEMO-1",
        "传输接入方式": "PON接入",
        "传输接入点的电路保护方式": "DEMO-1",
        "SVLAN": "DEMO-1",
        "CVLAN": "DEMO-1",
        "用户地址": "192.0.2.11",
        "网关地址": "192.0.2.11",
        "IPV4地址数": "192.0.2.11",
        "子接口": "DEMO-1",
        "数据网局端设备名称": "DEMO-1",
        "数据网局端设备端口名称": "DEMO-1",
        "数据网局端设备名称2": "",
        "数据网局端设备端口名称2": "",
        "客户端设备所属区域": "示例区1",
        "客户端所属机房": "DEMO-1",
        "客户端所属站点": "DEMO-1",
        "客户端业务设备名称": "DEMO-1",
        "客户端业务设备端口名称": "DEMO-1",
        "客户端设备的维护单位": "DEMO-1",
        "地域属性": "DEMO-1",
        "OLT设备名称": "DEMO-1",
        "OLT端口名称": "DEMO-1",
        "接入分光器": "DEMO-1",
        "传输设备或ONU名称": "DEMO-1",
        "传输设备或ONU端口": "DEMO-1",
        "地市预留字段": "",
        "备注": "DEMO-1",
        "创建人名称": "DEMO-1",
        "创建时间": "2026-01-01 10:00:00",
        "修改人名称": "DEMO-1",
        "修改时间": "2026-01-01 10:00:00",
        "业务标签": "DEMO-1",
        "营销组实例ID": "DEMO-1",
        "营销组名称": "DEMO-1",
        "ID": "DEMO-1"
      }
    },
    {
      "id": 12032,
      "source_type": "IPVPN专线",
      "area": "示例区2",
      "customer_name": "示例企业2（虚构）",
      "product_number": "DEMO-2",
      "product_type": "政企IPVPN专线",
      "access_method": "PON接入",
      "bandwidth": "100",
      "order_no": "DEMO-2",
      "assurance_level": "金牌",
      "olt_port_name": "DEMO-2",
      "splitter_name": "DEMO-2",
      "user_address": "192.0.2.12",
      "gateway_address": "192.0.2.12",
      "service_status": "正使用",
      "open_time": "2026-01-01 10:00:00",
      "line_name": "DEMO-2",
      "raw_data": {
        "区域": "示例区2",
        "核查状态": "DEMO-2",
        "核查信息": "DEMO-2",
        "专线名称": "DEMO-2",
        "服开工单号": "DEMO-2",
        "产品实例编码": "DEMO-2",
        "产品号码": "DEMO-2",
        "产品类型编码": "DEMO-2",
        "产品类型": "政企IPVPN专线",
        "业务所属地市": "示例市",
        "业务相关地市": "示例市",
        "传输接入方式": "PON接入",
        "流程中业务状态": "DEMO-2",
        "业务状态": "正使用",
        "验收交维状态": "DEMO-2",
        "业务用途描述": "DEMO-2",
        "接入方案": "DEMO-2",
        "开通日期": "2026-01-01 10:00:00",
        "业务保障等级": "DEMO-2",
        "客户所属地市": "示例市",
        "客户名称": "示例企业2（虚构）",
        "客户集团编码": "DEMO-2",
        "客户配合联系人": "DEMO-2",
        "客户配合联系人电话": "DEMO-PHONE",
        "客户端业务设备名称": "DEMO-2",
        "客户端业务设备端口名称": "DEMO-2",
        "客户端设备所属区县": "示例区2",
        "客户端设备的维护单位": "DEMO-2",
        "客户机房地址": "DEMO-2",
        "故障修复时限签约承诺": "DEMO-2",
        "来源类型": "IPVPN专线",
        "业务带宽": "100",
        "子产品类型": "DEMO-2",
        "传输接入点的电路保护方式": "DEMO-2",
        "传输电路名称": "DEMO-2",
        "SVLAN": "DEMO-2",
        "CVLAN": "DEMO-2",
        "接入分光器": "DEMO-2",
        "光路名称": "DEMO-2",
        "IPV4地址数": "192.0.2.12",
        "子接口": "DEMO-2",
        "数据网局端设备名称": "DEMO-2",
        "数据网局端设备端口名称": "DEMO-2",
        "数据网局端设备名称2": "",
        "数据网局端设备端口名称2": "",
        "用户地址": "192.0.2.12",
        "网关地址": "192.0.2.12",
        "地域属性": "DEMO-2",
        "传输设备或ONU名称": "DEMO-2",
        "传输设备或ONU端口": "DEMO-2",
        "OLT设备名称": "DEMO-2",
        "OLT端口名称": "DEMO-2",
        "地市预留字段": "",
        "VPN组网结构": "DEMO-2",
        "VPN名称": "DEMO-2",
        "VPN RD": "DEMO-2",
        "VPN等级": "DEMO-2",
        "VPN接入类型": "DEMO-2",
        "主站RT_IMPORT": "DEMO-2",
        "主站RT_EXPORT": "DEMO-2",
        "分站RT_IMPORT": "DEMO-2",
        "分站RT_EXPORT": "DEMO-2",
        "RT_IMPORT": "DEMO-2",
        "RT_EXPORT": "DEMO-2",
        "站点属性": "DEMO-2",
        "CE-PE路由协议": "DEMO-2",
        "自带局端互联IP": "192.0.2.12",
        "自带客户端互联IP": "192.0.2.12",
        "自带客户业务应用地址段": "DEMO-2",
        "自带IP": "192.0.2.12",
        "数据来源": "DEMO-2",
        "调度中产品号码": "DEMO-2",
        "客户类型": "DEMO-2",
        "楼宇编码": "DEMO-2",
        "楼宇名称": "DEMO-2",
        "备注": "DEMO-2",
        "创建人名称": "DEMO-2",
        "创建时间": "2026-01-01 10:00:00",
        "修改人名称": "DEMO-2",
        "修改时间": "2026-01-01 10:00:00"
      }
    },
    {
      "id": 12033,
      "source_type": "多媒体语音专线",
      "area": "示例区3",
      "customer_name": "示例企业3（虚构）",
      "product_number": "DEMO-3",
      "product_type": "多媒体语音专线",
      "access_method": "PON接入",
      "bandwidth": "100",
      "order_no": "DEMO-3",
      "assurance_level": "标准",
      "olt_port_name": "DEMO-3",
      "splitter_name": "DEMO-3",
      "user_address": "192.0.2.13",
      "gateway_address": "192.0.2.13",
      "service_status": "正使用",
      "open_time": "2026-01-01 10:00:00",
      "line_name": "DEMO-3",
      "raw_data": {
        "区域": "示例区3",
        "核查状态": "DEMO-3",
        "核查信息": "DEMO-3",
        "是否拓扑完整": "DEMO-3",
        "服开工单号": "DEMO-3",
        "业务所属地市": "示例市",
        "业务相关地市": "示例市",
        "工单类型": "DEMO-3",
        "产品号码": "DEMO-3",
        "产品实例编码": "DEMO-3",
        "产品类型编码": "DEMO-3",
        "产品类型": "多媒体语音专线",
        "子产品类型": "DEMO-3",
        "开通时间": "2026-01-01 10:00:00",
        "客户配合联系人": "DEMO-3",
        "客户配合联系人电话": "DEMO-PHONE",
        "客户所属地市": "示例市",
        "客户集团编码": "DEMO-3",
        "客户名称": "示例企业3（虚构）",
        "专线名称": "DEMO-3",
        "验收交维状态": "DEMO-3",
        "业务保障等级": "DEMO-3",
        "业务状态": "正使用",
        "来源类型": "多媒体语音专线",
        "业务带宽": "100",
        "SVLAN": "DEMO-3",
        "CVLAN": "DEMO-3",
        "网关地址": "192.0.2.13",
        "用户地址": "192.0.2.13",
        "客户机房地址": "DEMO-3",
        "客户端所属区县": "示例区3",
        "客户端业务设备名称": "DEMO-3",
        "客户端业务设备端口名称": "DEMO-3",
        "传输接入方式": "PON接入",
        "传输电路名称": "DEMO-3",
        "光路名称": "DEMO-3",
        "接入分光器": "DEMO-3",
        "传输设备或ONU名称": "DEMO-3",
        "传输设备或ONU端口": "DEMO-3",
        "OLT设备名称": "DEMO-3",
        "OLT端口名称": "DEMO-3",
        "楼宇编码": "DEMO-3",
        "楼宇名称": "DEMO-3",
        "业务标签": "DEMO-3",
        "营销组实例ID": "DEMO-3",
        "营销组名称": "DEMO-3",
        "备注": "DEMO-3"
      }
    },
    {
      "id": 12034,
      "source_type": "商务快线",
      "area": "示例区4",
      "customer_name": "示例企业4（虚构）",
      "product_number": "DEMO-4",
      "product_type": "商务快线",
      "access_method": "PON接入",
      "bandwidth": "100",
      "order_no": "DEMO-4",
      "assurance_level": "标准",
      "olt_port_name": "DEMO-4",
      "splitter_name": "DEMO-4",
      "building_name": "DEMO-4",
      "onu_port_name": "DEMO-4",
      "service_status": "正使用",
      "open_time": "2026-01-01 10:00:00",
      "line_name": "DEMO-4",
      "raw_data": {
        "区域": "示例区4",
        "客户所属地市": "示例市",
        "客户集团编码": "DEMO-4",
        "客户名称": "示例企业4（虚构）",
        "客户类型": "DEMO-4",
        "业务所属地市": "示例市",
        "业务相关地市": "示例市",
        "产品号码": "DEMO-4",
        "调度中产品号码": "DEMO-4",
        "产品实例编码": "DEMO-4",
        "产品类型编码": "DEMO-4",
        "产品类型名称": "DEMO-4",
        "服开工单号": "DEMO-4",
        "业务保障等级": "DEMO-4",
        "验收交维状态": "DEMO-4",
        "客户配合联系人": "DEMO-4",
        "客户配合联系人电话": "DEMO-PHONE",
        "业务带宽": "100",
        "业务状态": "正使用",
        "流程中业务状态": "DEMO-4",
        "开通日期": "2026-01-01 10:00:00",
        "数据来源": "DEMO-4",
        "来源类型": "商务快线",
        "客户机房地址": "DEMO-4",
        "专线名称": "DEMO-4",
        "传输接入方式": "PON接入",
        "光路名称": "DEMO-4",
        "SVLAN": "DEMO-4",
        "CVLAN": "DEMO-4",
        "楼宇编码": "DEMO-4",
        "楼宇名称": "DEMO-4",
        "传输设备或ONU名称": "DEMO-4",
        "传输设备或ONU端口": "DEMO-4",
        "OLT设备名称": "DEMO-4",
        "OLT端口名称": "DEMO-4",
        "上行带宽": "100",
        "下行带宽": "100",
        "接入分光器": "DEMO-4",
        "地市预留字段": "",
        "业务用途描述": "DEMO-4",
        "备注": "DEMO-4",
        "业务标签": "DEMO-4",
        "营销组实例ID": "DEMO-4",
        "营销组名称": "DEMO-4",
        "ID": "DEMO-4"
      }
    },
    {
      "id": 12035,
      "source_type": "传输专线",
      "area": "示例区5",
      "customer_name": "示例企业5（虚构）",
      "product_number": "DEMO-5",
      "product_type": "传输专线",
      "access_method": "OTN接入",
      "bandwidth": "100",
      "order_no": "DEMO-5",
      "assurance_level": "钻石",
      "a_end_transport_device_name": "DEMO-5",
      "z_end_transport_device_name": "DEMO-5",
      "transmission_circuit_display": "DEMO-5",
      "related_city": "示例市",
      "service_status": "正使用",
      "open_time": "2026-01-01 10:00:00",
      "line_name": "DEMO-5",
      "raw_data": {
        "区域": "示例区5",
        "核查状态": "DEMO-5",
        "核查信息": "DEMO-5",
        "是否拓扑完整": "DEMO-5",
        "客户所属地市": "示例市",
        "客户类型": "DEMO-5",
        "集团客户编码": "DEMO-5",
        "客户名称": "示例企业5（虚构）",
        "业务所属地市": "示例市",
        "业务相关地市": "示例市",
        "产品类型编码": "DEMO-5",
        "产品号码": "DEMO-5",
        "产品实例编码": "DEMO-5",
        "调度中产品号码": "DEMO-5",
        "产品类型": "传输专线",
        "子产品类型": "DEMO-5",
        "服开工单号": "DEMO-5",
        "工单类型": "DEMO-5",
        "开通时间": "2026-01-01 10:00:00",
        "业务状态": "正使用",
        "流程中业务状态": "DEMO-5",
        "业务保障等级": "DEMO-5",
        "验收交维状态": "DEMO-5",
        "数据来源": "DEMO-5",
        "专线名称": "DEMO-5",
        "客户配合联系人": "DEMO-5",
        "客户配合联系人电话": "DEMO-PHONE",
        "业务带宽": "100",
        "电路名称": "DEMO-5",
        "传输电路路由": "DEMO-5",
        "传输电路别名": "DEMO-5",
        "光路名称": "DEMO-5",
        "A端省份名称": "示例市",
        "A端地市名称": "示例市",
        "A端客户机房地址": "DEMO-5",
        "A端楼宇名称": "DEMO-5",
        "A端客户名称": "示例企业5（虚构）",
        "A端接口类型": "DEMO-5",
        "A端所属区县": "示例区5",
        "A端设备维护单位": "DEMO-5",
        "A端传输接入方式": "DEMO-5",
        "A端客户端业务设备": "DEMO-5",
        "A端客户端业务设备端口": "DEMO-5",
        "A端传输设备名称": "DEMO-5",
        "A端传输设备端口名称": "DEMO-5",
        "A端客户配合联系人": "DEMO-5",
        "A端客户配合联系人电话": "DEMO-PHONE",
        "A端光路名称": "DEMO-5",
        "Z端省份名称": "示例市",
        "Z端地市名称": "示例市",
        "Z端客户机房地址": "DEMO-5",
        "Z端客户名称": "示例企业5（虚构）",
        "Z端接口类型": "DEMO-5",
        "Z端所属区县": "示例区5",
        "Z端设备维护单位": "DEMO-5",
        "Z端传输接入方式": "DEMO-5",
        "Z端客户配合联系人": "DEMO-5",
        "Z端客户配合联系人电话": "DEMO-PHONE",
        "Z端客户端业务设备": "DEMO-5",
        "Z端客户端业务设备端口": "DEMO-5",
        "Z端传输设备名称": "DEMO-5",
        "Z端传输设备端口名称": "DEMO-5",
        "Z端光路名称": "DEMO-5",
        "A端楼宇编码": "DEMO-5",
        "Z端楼宇编码": "DEMO-5",
        "Z端楼宇名称": "DEMO-5",
        "业务标签": "DEMO-5",
        "营销组实例ID": "DEMO-5",
        "营销组名称": "DEMO-5"
      }
    }
  ],
  "onuItems": [
    {
      "id": 801,
      "onuid": "DEMO-1",
      "onu_name": "DEMO-1",
      "model": "HG8245H",
      "onu_vendor": "华为",
      "product_number": "DEMO-1",
      "customer_name": "示例企业1（虚构）",
      "service_type": "IPVPN专线",
      "client_county": "示例区1",
      "sn_code": "DEMO-SN-1",
      "onu_password": "DEMO-NOT-A-CREDENTIAL",
      "raw_data": {
        "ONUID": "DEMO-1",
        "ONU所属地市": "示例市",
        "ONU名称": "DEMO-1",
        "型号": "HG8245H",
        "设备种类": "DEMO-1",
        "ONU厂家": "华为",
        "ONU认证方式": "SN认证",
        "SN码": "DEMO-SN-1",
        "ONU密码": "DEMO-NOT-A-CREDENTIAL",
        "OLT管理IP": "192.0.2.11",
        "OLT所属地市": "示例市",
        "OLT厂家": "DEMO-1",
        "PONID": "DEMO-1",
        "产品号码": "DEMO-1",
        "客户名称": "示例企业1（虚构）",
        "业务类型": "IPVPN专线",
        "客户端设备所属区县": "示例区1"
      }
    },
    {
      "id": 802,
      "onuid": "DEMO-2",
      "onu_name": "DEMO-2",
      "model": "AN5506-04",
      "onu_vendor": "中兴",
      "product_number": "DEMO-2",
      "customer_name": "示例企业2（虚构）",
      "service_type": "IPVPN专线",
      "client_county": "示例区2",
      "sn_code": "DEMO-SN-2",
      "onu_password": "DEMO-NOT-A-CREDENTIAL",
      "raw_data": {
        "ONUID": "DEMO-2",
        "ONU所属地市": "示例市",
        "ONU名称": "DEMO-2",
        "型号": "AN5506-04",
        "设备种类": "DEMO-2",
        "ONU厂家": "中兴",
        "ONU认证方式": "密码认证",
        "SN码": "DEMO-SN-2",
        "ONU密码": "DEMO-NOT-A-CREDENTIAL",
        "OLT管理IP": "192.0.2.12",
        "OLT所属地市": "示例市",
        "OLT厂家": "DEMO-2",
        "PONID": "DEMO-2",
        "产品号码": "DEMO-2",
        "客户名称": "示例企业2（虚构）",
        "业务类型": "IPVPN专线",
        "客户端设备所属区县": "示例区2"
      }
    }
  ],
  "areaStats": [
    {
      "area": "示例区1",
      "source_type": "互联网专线",
      "total": 1
    },
    {
      "area": "示例区2",
      "source_type": "IPVPN专线",
      "total": 1
    },
    {
      "area": "示例区3",
      "source_type": "多媒体语音专线",
      "total": 1
    },
    {
      "area": "示例区4",
      "source_type": "商务快线",
      "total": 1
    },
    {
      "area": "示例区5",
      "source_type": "传输专线",
      "total": 1
    }
  ],
  "batches": [],
  "roles": [
    {
      "name": "viewer"
    },
    {
      "name": "exporter"
    },
    {
      "name": "admin"
    }
  ],
  "users": [
    {
      "id": 1,
      "username": "demo",
      "display_name": "演示管理员（虚构）",
      "roles": [
        "admin"
      ],
      "is_active": true,
      "active_sessions": 0
    }
  ],
  "sessions": [],
  "importErrors": [],
  "adminLogs": [],
  "adminSummary": {
    "import_data_dir": "./data/excel",
    "totals": {
      "line_total": 5,
      "onu_total": 2,
      "user_total": 1,
      "batch_total": 0,
      "active_sessions": 0
    },
    "line_breakdown": [
      {
        "source_type": "互联网专线",
        "total": 1
      },
      {
        "source_type": "IPVPN专线",
        "total": 1
      },
      {
        "source_type": "多媒体语音专线",
        "total": 1
      },
      {
        "source_type": "商务快线",
        "total": 1
      },
      {
        "source_type": "传输专线",
        "total": 1
      }
    ],
    "onu_breakdown": [
      {
        "service_type": "IPVPN专线",
        "total": 1
      },
      {
        "service_type": "IPVPN专线",
        "total": 1
      }
    ],
    "latest_batch": null
  }
};

const state = {
  module: "lines",
  line: {
    page: 1,
    size: 20,
    total: 0,
    items: [],
    filters: {},
    activeSourceType: "",
  },
  onu: {
    page: 1,
    size: 20,
    total: 0,
    items: [],
    filters: {},
  },
  batches: [],
  admin: {
    roles: [],
    users: [],
    sessions: [],
    logs: [],
    sessionUserId: "",
    dataSummary: null,
    importErrors: [],
  },
  auth: {
    token: "",
    user: null,
  },
};

const els = {
  currentDate: document.getElementById("currentDate"),
  currentUser: document.getElementById("currentUser"),
  refreshDashboardBtn: document.getElementById("refreshDashboardBtn"),
  logoutBtn: document.getElementById("logoutBtn"),

  areaBars: document.getElementById("areaBars"),
  kpiLines: document.getElementById("kpiLines"),
  kpiOnu: document.getElementById("kpiOnu"),
  kpiAreaCount: document.getElementById("kpiAreaCount"),
  kpiBatchStatus: document.getElementById("kpiBatchStatus"),

  lineFilterForm: document.getElementById("lineFilterForm"),
  lineTable: document.getElementById("lineTable"),
  lineTableHead: document.getElementById("lineTableHead"),
  lineTableBody: document.getElementById("lineTableBody"),
  lineEmpty: document.getElementById("lineEmpty"),
  linePageInfo: document.getElementById("linePageInfo"),
  linePrevBtn: document.getElementById("linePrevBtn"),
  lineNextBtn: document.getElementById("lineNextBtn"),
  lineExportBtn: document.getElementById("lineExportBtn"),

  onuFilterForm: document.getElementById("onuFilterForm"),
  onuTable: document.getElementById("onuTable"),
  onuTableHead: document.getElementById("onuTableHead"),
  onuTableBody: document.getElementById("onuTableBody"),
  onuEmpty: document.getElementById("onuEmpty"),
  onuPageInfo: document.getElementById("onuPageInfo"),
  onuPrevBtn: document.getElementById("onuPrevBtn"),
  onuNextBtn: document.getElementById("onuNextBtn"),
  onuExportBtn: document.getElementById("onuExportBtn"),

  batchRefreshBtn: document.getElementById("batchRefreshBtn"),
  batchTableBody: document.getElementById("batchTableBody"),
  batchEmpty: document.getElementById("batchEmpty"),

  adminDataRefreshBtn: document.getElementById("adminDataRefreshBtn"),
  adminDryRunBtn: document.getElementById("adminDryRunBtn"),
  adminImportBtn: document.getElementById("adminImportBtn"),
  adminImportDir: document.getElementById("adminImportDir"),
  adminImportStatus: document.getElementById("adminImportStatus"),
  adminLineTotal: document.getElementById("adminLineTotal"),
  adminOnuTotal: document.getElementById("adminOnuTotal"),
  adminUserTotal: document.getElementById("adminUserTotal"),
  adminBatchTotal: document.getElementById("adminBatchTotal"),
  adminSessionTotal: document.getElementById("adminSessionTotal"),
  adminLineBreakdown: document.getElementById("adminLineBreakdown"),
  adminOnuBreakdown: document.getElementById("adminOnuBreakdown"),
  adminLatestBatch: document.getElementById("adminLatestBatch"),
  importErrorRefreshBtn: document.getElementById("importErrorRefreshBtn"),
  importErrorTableBody: document.getElementById("importErrorTableBody"),
  importErrorEmpty: document.getElementById("importErrorEmpty"),
  adminLogRefreshBtn: document.getElementById("adminLogRefreshBtn"),
  adminLogTableBody: document.getElementById("adminLogTableBody"),
  adminLogEmpty: document.getElementById("adminLogEmpty"),

  userRefreshBtn: document.getElementById("userRefreshBtn"),
  userCreateForm: document.getElementById("userCreateForm"),
  userCreateRole: document.getElementById("userCreateRole"),
  userCreateSubmitBtn: document.getElementById("userCreateSubmitBtn"),
  userActionStatus: document.getElementById("userActionStatus"),
  userTableBody: document.getElementById("userTableBody"),
  userEmpty: document.getElementById("userEmpty"),
  sessionUserFilter: document.getElementById("sessionUserFilter"),
  sessionRefreshBtn: document.getElementById("sessionRefreshBtn"),
  sessionTableBody: document.getElementById("sessionTableBody"),
  sessionEmpty: document.getElementById("sessionEmpty"),

  drawer: document.getElementById("detailDrawer"),
  drawerTitle: document.getElementById("drawerTitle"),
  drawerRaw: document.getElementById("drawerRaw"),
  drawerCloseBtn: document.getElementById("drawerCloseBtn"),

  authGate: document.getElementById("authGate"),
  loginForm: document.getElementById("loginForm"),
  loginError: document.getElementById("loginError"),
};

function hasPermission(code) {
  const permissions = state.auth.user?.permissions || [];
  return permissions.includes(code);
}

function isAdmin() {
  return hasPermission("user.manage");
}

function setInlineStatus(element, message, isError = false) {
  if (!element) return;
  element.textContent = message;
  element.style.color = isError ? "var(--danger)" : "var(--muted)";
}

function saveToken(token) {
  state.auth.token = token;
  if (PREVIEW_MODE) return;
  if (token) {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

function setSession(token, user) {
  saveToken(token);
  state.auth.user = user;
  updateAuthUI();
}

function clearSession() {
  saveToken("");
  state.auth.user = null;
  updateAuthUI();
}

function updateAuthUI() {
  const user = state.auth.user;
  if (user) {
    const roleText = (user.roles || []).join(", ") || "-";
    els.currentUser.textContent = `${user.display_name} (${roleText})`;
    els.logoutBtn.classList.remove("perm-hidden");
  } else {
    els.currentUser.textContent = "未登录";
    els.logoutBtn.classList.add("perm-hidden");
  }

  const canExport = hasPermission("data.export");
  document.querySelectorAll(".perm-export").forEach((node) => {
    node.classList.toggle("perm-hidden", !canExport);
  });

  const canManage = isAdmin();
  document.querySelectorAll(".perm-admin").forEach((node) => {
    node.classList.toggle("perm-hidden", !canManage);
  });
}

function showAuthGate(message = "") {
  els.authGate.classList.add("open");
  els.loginError.textContent = message;
}

function hideAuthGate() {
  els.authGate.classList.remove("open");
  els.loginError.textContent = "";
}

function escapeHTML(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN", { hour12: false });
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("zh-CN");
}

function compactParams(obj) {
  const params = new URLSearchParams();
  Object.entries(obj).forEach(([key, value]) => {
    if (value === null || value === undefined) return;
    const text = String(value).trim();
    if (text === "") return;
    params.set(key, text);
  });
  return params;
}

function textIncludes(value, keyword) {
  const left = String(value || "").toLowerCase();
  const right = String(keyword || "").trim().toLowerCase();
  if (!right) return true;
  return left.includes(right);
}

function filterPreviewLines(params = {}) {
  let items = [...previewData.lineItems];
  if (params.source_type) {
    items = items.filter((item) => item.source_type === params.source_type);
  }
  if (params.area) {
    items = items.filter((item) => textIncludes(item.area, params.area));
  }
  if (params.customer_name) {
    items = items.filter((item) => textIncludes(item.customer_name, params.customer_name));
  }
  if (params.product_number) {
    items = items.filter((item) => String(item.product_number || "") === String(params.product_number || ""));
  }
  if (params.service_status) {
    items = items.filter((item) => textIncludes(item.service_status, params.service_status));
  }
  if (params.keyword) {
    items = items.filter((item) =>
      [item.customer_name, item.product_number, item.line_name, item.transmission_circuit_display, item.related_city]
        .some((value) => textIncludes(value, params.keyword))
    );
  }
  return items;
}

function filterPreviewOnu(params = {}) {
  let items = [...previewData.onuItems];
  if (params.service_type) {
    items = items.filter((item) => item.service_type === params.service_type);
  }
  if (params.product_number) {
    items = items.filter((item) => String(item.product_number || "") === String(params.product_number || ""));
  }
  if (params.sn_code) {
    items = items.filter((item) => textIncludes(item.sn_code, params.sn_code));
  }
  if (params.customer_name) {
    items = items.filter((item) => textIncludes(item.customer_name, params.customer_name));
  }
  if (params.client_county) {
    items = items.filter((item) => textIncludes(item.client_county, params.client_county));
  }
  if (params.keyword) {
    items = items.filter((item) =>
      [item.onuid, item.onu_name, item.sn_code, item.customer_name, item.product_number].some((value) => textIncludes(value, params.keyword))
    );
  }
  return items;
}

async function requestJSON(path, options = {}) {
  const { method = "GET", params = {}, body = null, auth = true } = options;

  if (PREVIEW_MODE) {
    const lineDetailMatch = path.match(/^\/api\/lines\/(\d+)$/);
    const onuDetailMatch = path.match(/^\/api\/onu\/(\d+)$/);
    const lineColumns = getLineColumns(params.source_type);

    if (path === "/api/auth/me") return { user: previewUser };
    if (path === "/api/auth/login") return { access_token: "preview-token", user: previewUser };
    if (path === "/api/auth/logout") return {};
    if (path === "/api/lines/search") {
      const filtered = filterPreviewLines(params);
      const page = Number(params.page || 1);
      const size = Number(params.size || 20);
      const offset = Math.max(0, (page - 1) * size);
      return { items: filtered.slice(offset, offset + size), total: filtered.length };
    }
    if (path === "/api/lines/export") {
      return {
        items: filterPreviewLines(params).map((item) => {
          const row = {};
          lineColumns.forEach((column) => {
            row[column.label] = item[column.key] ?? "";
          });
          return row;
        }),
      };
    }
    if (lineDetailMatch) {
      return previewData.lineItems.find((item) => item.id === Number(lineDetailMatch[1])) || previewData.lineItems[0];
    }
    if (path === "/api/onu/search") {
      const filtered = filterPreviewOnu(params);
      const page = Number(params.page || 1);
      const size = Number(params.size || 20);
      const offset = Math.max(0, (page - 1) * size);
      return { items: filtered.slice(offset, offset + size), total: filtered.length };
    }
    if (path === "/api/onu/export") {
      return {
        items: filterPreviewOnu(params).map((item) => ({
          区县: item.client_county ?? "",
          客户名称: item.customer_name ?? "",
          业务类型: item.service_type ?? "",
          产品号码: item.product_number ?? "",
          厂家: item.onu_vendor ?? "",
          型号: item.model ?? "",
          SN码: item.sn_code ?? "",
          ONU密码: item.onu_password ?? "",
          ONU名称: item.onu_name ?? "",
        })),
      };
    }
    if (onuDetailMatch) {
      return previewData.onuItems.find((item) => item.id === Number(onuDetailMatch[1])) || previewData.onuItems[0];
    }
    if (path === "/api/stats/by-area") return { items: previewData.areaStats };
    if (path === "/api/import/batches") return { items: previewData.batches.slice(0, Number(params.limit || 20)) };
    if (path === "/api/admin/roles") return { items: previewData.roles };
    if (path === "/api/admin/users") return { items: previewData.users };
    if (path === "/api/admin/sessions") return { items: previewData.sessions };
    if (path === "/api/admin/data/summary") return previewData.adminSummary;
    if (path === "/api/admin/import/errors") return { items: previewData.importErrors };
    if (path === "/api/admin/logs") return { items: previewData.adminLogs };
    if (method !== "GET") return {};
    throw new Error("预览模式不访问真实接口");
  }

  const query = compactParams(params).toString();
  const url = query ? `${path}?${query}` : path;
  const headers = { Accept: "application/json" };

  if (body !== null) {
    headers["Content-Type"] = "application/json";
  }
  if (auth && state.auth.token) {
    headers.Authorization = `Bearer ${state.auth.token}`;
  }

  const response = await fetch(url, {
    method,
    headers,
    body: body !== null ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json();
      detail = payload.detail || JSON.stringify(payload);
    } catch {
      detail = await response.text();
    }

    if (auth && response.status === 401) {
      clearSession();
      showAuthGate("登录已失效，请重新登录");
    }
    throw new Error(`HTTP ${response.status}: ${detail || path}`);
  }

  if (response.status === 204) return {};
  return response.json();
}

function setTableEmpty(emptyEl, tbodyEl, isEmpty) {
  emptyEl.style.display = isEmpty ? "block" : "none";
  tbodyEl.style.display = isEmpty ? "none" : "";
}

function csvEscape(value) {
  if (value === null || value === undefined) return "";
  let safe = String(value);
  if (/^[\s]*[=+@-]|^[\t\r\n]/.test(safe)) safe = "'" + safe;
  const text = safe.replaceAll('"', '""');
  if (/[",\r\n]/.test(text)) return `"${text}"`;
  return text;
}

function exportToCSV(items, filenamePrefix) {
  if (!items || items.length === 0) {
    window.alert("当前没有可导出的数据");
    return;
  }
  const headers = Object.keys(items[0]);
  const lines = [headers.map(csvEscape).join(",")];
  items.forEach((row) => {
    lines.push(headers.map((header) => csvEscape(row[header])).join(","));
  });
  const content = `\ufeff${lines.join("\n")}`;
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${filenamePrefix}_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function statusClass(status) {
  const normalized = (status || "").toUpperCase();
  if (normalized.includes("SUCCESS")) return "success";
  if (normalized.includes("RUNNING") || normalized.includes("DRY")) return "running";
  if (normalized.includes("FAIL")) return "failed";
  return "";
}

function updateDateText() {
  const now = new Date();
  els.currentDate.textContent = now.toLocaleString("zh-CN", { hour12: false });
}

function renderAreaBars(items) {
  const areaMap = {};
  (items || []).forEach((item) => {
    const area = item.area || "未标注";
    const total = Number(item.total || 0);
    areaMap[area] = (areaMap[area] || 0) + total;
  });
  const topAreas = Object.entries(areaMap)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);

  if (topAreas.length === 0) {
    els.areaBars.innerHTML = '<div class="table-empty" style="display:block">暂无统计数据</div>';
    return;
  }

  const maxValue = topAreas[0][1] || 1;
  els.areaBars.innerHTML = topAreas
    .map(([area, total]) => {
      const width = Math.max(5, Math.round((total / maxValue) * 100));
      return `
        <div class="bar-row">
          <span class="bar-label">${escapeHTML(area)}</span>
          <div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div>
          <span class="bar-value">${formatNumber(total)}</span>
        </div>
      `;
    })
    .join("");
}

const LINE_COLUMNS_ALL = [
  { key: "area", label: "区域", width: 56, fixed: true },
  { key: "customer_name", label: "客户名称", width: 148 },
  { key: "product_type", label: "产品类型", width: 96, fixed: true },
  { key: "product_number", label: "产品号码", width: 112, className: "mono", fixed: true },
  { key: "bandwidth", label: "业务带宽", width: 96 },
  { key: "access_method", label: "传输接入方式", width: 84, fixed: true },
  { key: "open_time", label: "开通时间", format: "date", width: 160 },
  { key: "order_no", label: "服开工单号", width: 160, className: "mono" },
  { key: "assurance_level", label: "业务保障等级", width: 110 },
];

const LINE_COLUMNS_IP = [
  { key: "area", label: "区域", width: 56, fixed: true },
  { key: "customer_name", label: "客户名称", width: 148 },
  { key: "product_type", label: "产品类型", width: 96, fixed: true },
  { key: "product_number", label: "产品号码", width: 112, className: "mono", fixed: true },
  { key: "access_method", label: "传输接入方式", width: 84, fixed: true },
  { key: "olt_port_name", label: "OLT端口名称", width: 145, className: "mono" },
  { key: "splitter_name", label: "接入分光器", width: 140 },
  { key: "user_address", label: "IP地址", width: 190, className: "mono" },
  { key: "gateway_address", label: "网关地址", width: 142, className: "mono" },
];

const LINE_COLUMNS_BUSINESS = [
  { key: "area", label: "区域", width: 56, fixed: true },
  { key: "customer_name", label: "客户名称", width: 148 },
  { key: "product_type", label: "产品类型", width: 96, fixed: true },
  { key: "product_number", label: "产品号码", width: 112, className: "mono", fixed: true },
  { key: "access_method", label: "传输接入方式", width: 84, fixed: true },
  { key: "olt_port_name", label: "OLT端口名称", width: 145, className: "mono" },
  { key: "splitter_name", label: "接入分光器", width: 140 },
  { key: "building_name", label: "楼宇名称", width: 180 },
  { key: "onu_port_name", label: "传输设备或ONU端口", width: 180, className: "mono" },
];

const LINE_COLUMNS_TRANSPORT = [
  { key: "area", label: "区域", width: 56, fixed: true },
  { key: "customer_name", label: "客户名称", width: 148 },
  { key: "product_type", label: "产品类型", width: 96, fixed: true },
  { key: "product_number", label: "产品号码", width: 112, className: "mono", fixed: true },
  { key: "access_method", label: "传输接入方式", width: 84, fixed: true },
  { key: "a_end_transport_device_name", label: "A端传输设备名称", width: 180 },
  { key: "z_end_transport_device_name", label: "Z端传输设备名称", width: 180 },
  { key: "transmission_circuit_display", label: "电路名称", width: 180, className: "mono" },
  { key: "related_city", label: "业务相关地市", width: 120 },
];

const ONU_COLUMNS = [
  { key: "client_county", label: "区县", width: 72, fixed: true },
  { key: "customer_name", label: "客户名称", width: 220 },
  { key: "service_type", label: "业务类型", width: 108, fixed: true },
  { key: "product_number", label: "产品号码", width: 160, className: "mono" },
  { key: "onu_vendor", label: "厂家", width: 78, fixed: true },
  { key: "model", label: "型号", width: 140 },
  { key: "sn_code", label: "SN码", width: 180, className: "mono" },
  { key: "onu_password", label: "ONU密码", width: 140, className: "mono" },
  { key: "onu_name", label: "ONU名称", width: 220 },
];

function getLineColumns(sourceType = "") {
  if (["互联网专线", "IPVPN专线", "多媒体语音专线"].includes(sourceType)) {
    return LINE_COLUMNS_IP;
  }
  if (sourceType === "商务快线") {
    return LINE_COLUMNS_BUSINESS;
  }
  if (sourceType === "传输专线") {
    return LINE_COLUMNS_TRANSPORT;
  }
  return LINE_COLUMNS_ALL;
}

function getColumnClassName(column) {
  const names = [`col-${column.key}`];
  if (column.className) {
    names.push(column.className);
  }
  if (column.fixed) {
    names.push("is-fixed");
  }
  return names.join(" ");
}

function ensureTableColgroup(table) {
  if (!table) return null;
  let colgroup = table.querySelector("colgroup");
  if (!colgroup) {
    colgroup = document.createElement("colgroup");
    table.insertBefore(colgroup, table.firstChild);
  }
  return colgroup;
}

function applyTableLayout(table, columns) {
  if (!table) return;
  const totalWidth = columns.reduce((sum, column) => sum + Number(column.width || 120), 0) + 68;
  table.style.width = "100%";
  table.style.minWidth = `${totalWidth}px`;
  const colgroup = ensureTableColgroup(table);
  if (colgroup) {
    colgroup.innerHTML = [
      ...columns.map((column) => {
        const widthStyle = column.fixed ? ` style="width:${Number(column.width || 120)}px"` : "";
        return `<col class="${getColumnClassName(column)}"${widthStyle} />`;
      }),
      '<col class="col-actions is-fixed" style="width:68px" />',
    ].join("");
  }
}

function renderTableHead(target, table, columns) {
  if (!target) return;
  applyTableLayout(table, columns);
  target.innerHTML = `
    <tr>
      ${columns
        .map(
          (column) =>
            `<th class="${getColumnClassName(column)}"${column.fixed ? ` style="width:${Number(column.width || 120)}px"` : ""}>${escapeHTML(column.label)}</th>`
        )
        .join("")}
      <th class="col-actions" style="width:68px">操作</th>
    </tr>
  `;
}

function formatTableCell(item, column) {
  const value = item?.[column.key];
  if (column.format === "date") return formatDate(value);
  return value ?? "-";
}

function renderLineTable() {
  const items = state.line.items;
  const columns = getLineColumns(state.line.activeSourceType);
  renderTableHead(els.lineTableHead, els.lineTable, columns);
  setTableEmpty(els.lineEmpty, els.lineTableBody, items.length === 0);
  if (items.length === 0) {
    els.lineTableBody.innerHTML = "";
    return;
  }

  els.lineTableBody.innerHTML = items
    .map(
      (item) => `
        <tr>
          ${columns
            .map(
              (column) =>
                `<td class="${getColumnClassName(column)}">${escapeHTML(formatTableCell(item, column))}</td>`
            )
            .join("")}
          <td class="col-actions"><button class="btn btn-ghost js-line-detail" data-id="${item.id}">详情</button></td>
        </tr>
      `
    )
    .join("");
}

function renderOnuTable() {
  const items = state.onu.items;
  renderTableHead(els.onuTableHead, els.onuTable, ONU_COLUMNS);
  setTableEmpty(els.onuEmpty, els.onuTableBody, items.length === 0);
  if (items.length === 0) {
    els.onuTableBody.innerHTML = "";
    return;
  }

  els.onuTableBody.innerHTML = items
    .map(
      (item) => `
        <tr>
          ${ONU_COLUMNS
            .map(
              (column) =>
                `<td class="${getColumnClassName(column)}">${escapeHTML(formatTableCell(item, column))}</td>`
            )
            .join("")}
          <td class="col-actions"><button class="btn btn-ghost js-onu-detail" data-id="${item.id}">详情</button></td>
        </tr>
      `
    )
    .join("");
}

function renderBatchTable() {
  const items = state.batches;
  setTableEmpty(els.batchEmpty, els.batchTableBody, items.length === 0);
  if (items.length === 0) {
    els.batchTableBody.innerHTML = "";
    return;
  }

  els.batchTableBody.innerHTML = items
    .map((item) => {
      const chipClass = statusClass(item.status);
      return `
        <tr>
          <td>${item.id ?? "-"}</td>
          <td>${escapeHTML(item.batch_name)}</td>
          <td><span class="status-chip ${chipClass}">${escapeHTML(item.status)}</span></td>
          <td>${formatNumber(item.files_total)}</td>
          <td>${formatNumber(item.rows_processed)}</td>
          <td>${formatNumber(item.rows_affected)}</td>
          <td>${formatNumber(item.rows_failed)}</td>
          <td>${escapeHTML(formatDate(item.started_at))}</td>
          <td>${escapeHTML(formatDate(item.finished_at))}</td>
          <td>${escapeHTML(item.message)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderMetricList(target, items, labelKey) {
  if (!target) return;
  if (!items || items.length === 0) {
    target.innerHTML = '<div class="table-empty" style="display:block">暂无数据</div>';
    return;
  }

  target.innerHTML = items
    .map(
      (item) => `
        <div class="metric-item">
          <span class="metric-label">${escapeHTML(item[labelKey] || "未标注")}</span>
          <span class="metric-value">${formatNumber(item.total)}</span>
        </div>
      `
    )
    .join("");
}

function renderLatestBatch(batch) {
  if (!els.adminLatestBatch) return;
  if (!batch) {
    els.adminLatestBatch.innerHTML = '<div class="table-empty" style="display:block">暂无批次</div>';
    return;
  }

  const fields = [
    ["批次名", batch.batch_name],
    ["状态", batch.status],
    ["开始时间", formatDate(batch.started_at)],
    ["完成时间", formatDate(batch.finished_at)],
    ["处理行数", formatNumber(batch.rows_processed)],
    ["写入行数", formatNumber(batch.rows_affected)],
    ["失败行数", formatNumber(batch.rows_failed)],
    ["说明", batch.message || "-"],
  ];

  els.adminLatestBatch.innerHTML = fields
    .map(
      ([label, value]) => `
        <div class="summary-item">
          <span class="label">${escapeHTML(label)}</span>
          <span class="value">${escapeHTML(value)}</span>
        </div>
      `
    )
    .join("");
}

function renderImportErrors() {
  const items = state.admin.importErrors;
  setTableEmpty(els.importErrorEmpty, els.importErrorTableBody, items.length === 0);
  if (items.length === 0) {
    els.importErrorTableBody.innerHTML = "";
    return;
  }

  els.importErrorTableBody.innerHTML = items
    .map(
      (item) => `
        <tr>
          <td>${item.id}</td>
          <td>${escapeHTML(item.batch_name)} (#${item.batch_id})</td>
          <td>${escapeHTML(item.source_file)}</td>
          <td>${escapeHTML(item.source_sheet)}</td>
          <td>${escapeHTML(item.source_row_number ?? "-")}</td>
          <td>${escapeHTML(item.error_message)}</td>
          <td>${escapeHTML(formatDate(item.created_at))}</td>
        </tr>
      `
    )
    .join("");
}

function summarizeLogDetail(detail) {
  if (!detail) return "-";
  if (typeof detail === "string") return detail;
  const text = JSON.stringify(detail, null, 0);
  return text.length > 120 ? `${text.slice(0, 117)}...` : text;
}

function renderRoleOptions(selectedRole = "") {
  const roles = state.admin.roles || [];
  if (roles.length === 0) {
    return '<option value="">暂无角色</option>';
  }
  return roles
    .map((role) => {
      const selected = role.name === selectedRole ? "selected" : "";
      return `<option value="${escapeHTML(role.name)}" ${selected}>${escapeHTML(role.name)}</option>`;
    })
    .join("");
}

function renderCreateRoleOptions() {
  if (!els.userCreateRole) return;
  els.userCreateRole.innerHTML = renderRoleOptions("viewer");
  const hasRoles = (state.admin.roles || []).length > 0;
  els.userCreateRole.disabled = !hasRoles;
  if (els.userCreateSubmitBtn) {
    els.userCreateSubmitBtn.disabled = !hasRoles;
  }
}

function renderSessionUserFilter() {
  if (!els.sessionUserFilter) return;
  const options = ['<option value="">全部用户</option>'];
  (state.admin.users || []).forEach((user) => {
    const selected = String(user.id) === String(state.admin.sessionUserId || "") ? "selected" : "";
    options.push(
      `<option value="${user.id}" ${selected}>${escapeHTML(user.username)} / ${escapeHTML(user.display_name)}</option>`
    );
  });
  els.sessionUserFilter.innerHTML = options.join("");

  if (
    state.admin.sessionUserId &&
    !(state.admin.users || []).some((user) => String(user.id) === String(state.admin.sessionUserId))
  ) {
    state.admin.sessionUserId = "";
    els.sessionUserFilter.value = "";
  }
}

function renderUserTable() {
  const items = state.admin.users;
  setTableEmpty(els.userEmpty, els.userTableBody, items.length === 0);
  if (items.length === 0) {
    els.userTableBody.innerHTML = "";
    return;
  }

  els.userTableBody.innerHTML = items
    .map((item) => {
      const isCurrent = Number(item.id) === Number(state.auth.user?.id || 0);
      const statusText = item.is_active ? "启用" : "停用";
      const statusChip = item.is_active ? "success" : "failed";
      return `
        <tr data-user-id="${item.id}" data-active="${item.is_active ? 1 : 0}">
          <td class="mono">
            ${escapeHTML(item.username)}
            ${isCurrent ? '<span class="self-badge">当前</span>' : ""}
          </td>
          <td>
            <input class="table-input js-user-display-name" value="${escapeHTML(item.display_name)}" />
          </td>
          <td>
            <select class="table-select js-user-role">${renderRoleOptions(item.roles?.[0] || "")}</select>
          </td>
          <td>
            <span class="status-chip ${statusChip}">${statusText}</span>
          </td>
          <td>${formatNumber(item.active_sessions)}</td>
          <td>${escapeHTML(formatDate(item.updated_at))}</td>
          <td>
            <div class="actions-row">
              <button class="btn btn-ghost js-user-save">保存</button>
              <button class="btn btn-ghost js-user-toggle">${item.is_active ? "停用" : "启用"}</button>
              <button class="btn btn-ghost js-user-revoke-all">强制下线</button>
              <button class="btn btn-ghost js-user-reset">重置密码</button>
              <button class="btn btn-ghost js-user-delete" ${isCurrent ? "disabled" : ""}>删除</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
}

function renderSessionTable() {
  const items = state.admin.sessions;
  setTableEmpty(els.sessionEmpty, els.sessionTableBody, items.length === 0);
  if (items.length === 0) {
    els.sessionTableBody.innerHTML = "";
    return;
  }

  els.sessionTableBody.innerHTML = items
    .map((item) => {
      const statusText = item.is_active ? "在线" : "已失效";
      const statusChip = item.is_active ? "success" : "failed";
      const rolesText = (item.roles || []).join(", ") || "-";
      const currentBadge = item.is_current ? '<span class="self-badge">当前</span>' : "";
      return `
        <tr data-session-id="${item.id}" data-user-id="${item.user_id}">
          <td class="mono">#${item.id}</td>
          <td>
            ${escapeHTML(item.username)}
            ${currentBadge}
            <div class="table-subtext">${escapeHTML(item.display_name || "-")}</div>
          </td>
          <td>${escapeHTML(rolesText)}</td>
          <td><span class="status-chip ${statusChip}">${statusText}</span></td>
          <td class="mono">${escapeHTML(item.ip_address || "-")}</td>
          <td>${escapeHTML(formatDate(item.created_at))}</td>
          <td>${escapeHTML(formatDate(item.expires_at))}</td>
          <td class="table-subtext clamp-text">${escapeHTML(item.user_agent || "-")}</td>
          <td>
            <button class="btn btn-ghost js-session-revoke" ${item.is_current ? "disabled" : ""}>强制下线</button>
          </td>
        </tr>
      `;
    })
    .join("");
}

function renderAdminLogs() {
  const items = state.admin.logs;
  setTableEmpty(els.adminLogEmpty, els.adminLogTableBody, items.length === 0);
  if (items.length === 0) {
    els.adminLogTableBody.innerHTML = "";
    return;
  }

  els.adminLogTableBody.innerHTML = items
    .map(
      (item) => `
        <tr>
          <td>${escapeHTML(formatDate(item.created_at))}</td>
          <td>${escapeHTML(item.actor_username || "-")}</td>
          <td class="mono">${escapeHTML(item.action_code || "-")}</td>
          <td>${escapeHTML(item.target_label || `${item.target_type || "-"}#${item.target_id || "-"}`)}</td>
          <td><span class="status-chip ${statusClass(item.status)}">${escapeHTML(item.status || "-")}</span></td>
          <td class="table-subtext">
            <div>${escapeHTML(item.ip_address || "-")}</div>
            <div class="clamp-text">${escapeHTML(item.user_agent || "-")}</div>
          </td>
          <td class="table-subtext clamp-text">${escapeHTML(summarizeLogDetail(item.detail_json))}</td>
        </tr>
      `
    )
    .join("");
}

function updateLinePagination() {
  const totalPages = Math.max(1, Math.ceil(state.line.total / state.line.size));
  els.linePageInfo.textContent = `第 ${state.line.page} / ${totalPages} 页，共 ${formatNumber(state.line.total)} 条`;
  els.linePrevBtn.disabled = state.line.page <= 1;
  els.lineNextBtn.disabled = state.line.page >= totalPages;
}

function updateOnuPagination() {
  const totalPages = Math.max(1, Math.ceil(state.onu.total / state.onu.size));
  els.onuPageInfo.textContent = `第 ${state.onu.page} / ${totalPages} 页，共 ${formatNumber(state.onu.total)} 条`;
  els.onuPrevBtn.disabled = state.onu.page <= 1;
  els.onuNextBtn.disabled = state.onu.page >= totalPages;
}

async function refreshCurrentUser() {
  if (!state.auth.token) return;
  const data = await requestJSON("/api/auth/me");
  setSession(state.auth.token, data.user);
}

async function fetchLines() {
  if (!hasPermission("data.query")) return;
  state.line.activeSourceType = state.line.filters.source_type || "";
  const data = await requestJSON("/api/lines/search", {
    params: {
      page: state.line.page,
      size: state.line.size,
      ...state.line.filters,
    },
  });
  state.line.items = data.items || [];
  state.line.total = Number(data.total || 0);
  renderLineTable();
  updateLinePagination();
}

async function fetchOnu() {
  if (!hasPermission("data.query")) return;
  const data = await requestJSON("/api/onu/search", {
    params: {
      page: state.onu.page,
      size: state.onu.size,
      ...state.onu.filters,
    },
  });
  state.onu.items = data.items || [];
  state.onu.total = Number(data.total || 0);
  renderOnuTable();
  updateOnuPagination();
}

async function fetchBatches() {
  if (!hasPermission("data.query")) return;
  const data = await requestJSON("/api/import/batches", { params: { limit: 50 } });
  state.batches = data.items || [];
  renderBatchTable();
}

async function fetchAdminRoles() {
  if (!isAdmin()) return;
  const data = await requestJSON("/api/admin/roles");
  state.admin.roles = data.items || [];
  renderCreateRoleOptions();
  renderUserTable();
  if ((state.admin.roles || []).length === 0) {
    setInlineStatus(els.userActionStatus, "未读取到任何角色，请检查角色初始化", true);
  }
}

async function fetchAdminUsers() {
  if (!isAdmin()) return;
  const data = await requestJSON("/api/admin/users");
  state.admin.users = data.items || [];
  renderSessionUserFilter();
  renderUserTable();
}

async function fetchAdminSessions() {
  if (!isAdmin()) return;
  const params = { limit: 100 };
  if (state.admin.sessionUserId) {
    params.user_id = state.admin.sessionUserId;
  }
  const data = await requestJSON("/api/admin/sessions", { params });
  state.admin.sessions = data.items || [];
  renderSessionTable();
}

async function fetchAdminDataSummary() {
  if (!isAdmin()) return;
  const data = await requestJSON("/api/admin/data/summary");
  state.admin.dataSummary = data;

  els.adminImportDir.textContent = data.import_data_dir || "-";
  els.adminLineTotal.textContent = formatNumber(data.totals?.line_total || 0);
  els.adminOnuTotal.textContent = formatNumber(data.totals?.onu_total || 0);
  els.adminUserTotal.textContent = formatNumber(data.totals?.user_total || 0);
  els.adminBatchTotal.textContent = formatNumber(data.totals?.batch_total || 0);
  els.adminSessionTotal.textContent = formatNumber(data.totals?.active_sessions || 0);

  renderMetricList(els.adminLineBreakdown, data.line_breakdown || [], "source_type");
  renderMetricList(els.adminOnuBreakdown, data.onu_breakdown || [], "service_type");
  renderLatestBatch(data.latest_batch);
}

async function fetchImportErrors() {
  if (!isAdmin()) return;
  const data = await requestJSON("/api/admin/import/errors", { params: { limit: 100 } });
  state.admin.importErrors = data.items || [];
  renderImportErrors();
}

async function fetchAdminLogs() {
  if (!isAdmin()) return;
  const data = await requestJSON("/api/admin/logs", { params: { limit: 100 } });
  state.admin.logs = data.items || [];
  renderAdminLogs();
}

async function refreshAdminDataModule() {
  if (!isAdmin()) return;
  try {
    await Promise.all([fetchAdminDataSummary(), fetchImportErrors(), fetchAdminLogs()]);
  } catch (error) {
    console.error(error);
    setInlineStatus(els.adminImportStatus, "管理员数据加载失败", true);
  }
}

async function refreshAdminUsersModule() {
  if (!isAdmin()) return;
  try {
    await fetchAdminRoles();
    await fetchAdminUsers();
    await fetchAdminSessions();
  } catch (error) {
    console.error(error);
    setInlineStatus(els.userActionStatus, "用户或会话数据加载失败", true);
  }
}

async function refreshDashboard() {
  if (!hasPermission("data.query")) return;
  try {
    const [lineData, onuData, areaData, batchData] = await Promise.all([
      requestJSON("/api/lines/search", { params: { page: 1, size: 1 } }),
      requestJSON("/api/onu/search", { params: { page: 1, size: 1 } }),
      requestJSON("/api/stats/by-area"),
      requestJSON("/api/import/batches", { params: { limit: 1 } }),
    ]);

    els.kpiLines.textContent = formatNumber(lineData.total || 0);
    els.kpiOnu.textContent = formatNumber(onuData.total || 0);

    const areas = new Set((areaData.items || []).map((row) => row.area).filter(Boolean));
    els.kpiAreaCount.textContent = formatNumber(areas.size);
    renderAreaBars(areaData.items || []);

    const latestBatch = (batchData.items || [])[0];
    if (latestBatch) {
      els.kpiBatchStatus.textContent = `${latestBatch.status} (${formatDate(latestBatch.started_at)})`;
    } else {
      els.kpiBatchStatus.textContent = "-";
    }
  } catch (error) {
    console.error(error);
    els.kpiLines.textContent = "-";
    els.kpiOnu.textContent = "-";
    els.kpiAreaCount.textContent = "-";
    els.kpiBatchStatus.textContent = "加载失败";
  }
}

function closeDrawer() {
  els.drawer.classList.remove("open");
}

async function openLineDetail(id) {
  const detail = await requestJSON(`/api/lines/${id}`);
  els.drawerTitle.textContent = `专线详情 #${id}`;
  els.drawerRaw.textContent = JSON.stringify(detail.raw_data || detail, null, 2);
  els.drawer.classList.add("open");
}

async function openOnuDetail(id) {
  const detail = await requestJSON(`/api/onu/${id}`);
  els.drawerTitle.textContent = `ONU详情 #${id}`;
  els.drawerRaw.textContent = JSON.stringify(detail.raw_data || detail, null, 2);
  els.drawer.classList.add("open");
}

async function exportLines() {
  if (!hasPermission("data.export")) {
    window.alert("当前账号没有导出权限");
    return;
  }
  const data = await requestJSON("/api/lines/export", {
    params: {
      ...state.line.filters,
      limit: 5000,
    },
  });
  exportToCSV(data.items || [], "line_records_export");
}

async function exportOnu() {
  if (!hasPermission("data.export")) {
    window.alert("当前账号没有导出权限");
    return;
  }
  const data = await requestJSON("/api/onu/export", {
    params: {
      ...state.onu.filters,
      limit: 5000,
    },
  });
  exportToCSV(data.items || [], "onu_records_export");
}

async function runImport(dryRun) {
  const confirmText = dryRun ? "确认执行一次演练导入？不会写入业务数据。" : "确认执行正式导入？这会把 Excel 最新数据写入数据库。";
  if (!window.confirm(confirmText)) return;

  setInlineStatus(els.adminImportStatus, dryRun ? "正在发起演练导入..." : "正在发起正式导入...");
  try {
    const data = await requestJSON("/api/admin/import/run", {
      method: "POST",
      body: { dry_run: dryRun },
    });
    setInlineStatus(
      els.adminImportStatus,
      `${dryRun ? "演练" : "正式"}导入已启动，批次名 ${data.batch_name}，日志 ${data.log_file}`
    );
    window.setTimeout(async () => {
      try {
        await Promise.all([fetchBatches(), fetchAdminDataSummary(), fetchAdminLogs()]);
      } catch (error) {
        console.error(error);
      }
    }, 1500);
  } catch (error) {
    console.error(error);
    setInlineStatus(els.adminImportStatus, `导入启动失败：${error.message}`, true);
  }
}

async function createUser(payload) {
  const data = await requestJSON("/api/admin/users", {
    method: "POST",
    body: payload,
  });
  return data.user;
}

async function saveUser(userId, displayName, role) {
  const data = await requestJSON(`/api/admin/users/${userId}`, {
    method: "PATCH",
    body: {
      display_name: displayName,
      role,
    },
  });
  return data.user;
}

async function toggleUser(userId, nextActive) {
  const data = await requestJSON(`/api/admin/users/${userId}`, {
    method: "PATCH",
    body: {
      is_active: nextActive,
    },
  });
  return data.user;
}

async function resetUserPassword(userId, password) {
  await requestJSON(`/api/admin/users/${userId}/reset-password`, {
    method: "POST",
    body: { password },
  });
}

async function deleteUser(userId) {
  await requestJSON(`/api/admin/users/${userId}`, {
    method: "DELETE",
  });
}

async function revokeUserSessions(userId, reason = "") {
  const data = await requestJSON(`/api/admin/users/${userId}/revoke-sessions`, {
    method: "POST",
    body: { reason },
  });
  return data;
}

async function revokeSessionById(sessionId, reason = "") {
  const data = await requestJSON(`/api/admin/sessions/${sessionId}/revoke`, {
    method: "POST",
    body: { reason },
  });
  return data;
}

async function switchModule(module) {
  if ((module === "adminData" || module === "users") && !isAdmin()) {
    module = "lines";
  }

  state.module = module;
  document.querySelectorAll(".menu-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.module === module);
  });
  document.querySelectorAll(".module").forEach((section) => {
    section.classList.toggle("active", section.id === `${module}Module`);
  });

  try {
    if (module === "lines") await fetchLines();
    if (module === "onu") await fetchOnu();
    if (module === "analytics") await refreshDashboard();
    if (module === "imports") await fetchBatches();
    if (module === "adminData") await refreshAdminDataModule();
    if (module === "users") await refreshAdminUsersModule();
  } catch (error) {
    console.error(error);
    window.alert("模块数据加载失败，请稍后重试。");
  }
}

function bindModuleSwitcher() {
  document.querySelectorAll(".menu-item").forEach((item) => {
    item.addEventListener("click", async () => {
      await switchModule(item.dataset.module);
    });
  });
}

function bindLineEvents() {
  els.lineFilterForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(els.lineFilterForm);
    const filters = {};
    formData.forEach((value, key) => {
      const text = String(value).trim();
      if (text) filters[key] = text;
    });
    state.line.filters = filters;
    state.line.page = 1;
    try {
      await fetchLines();
    } catch (error) {
      console.error(error);
      window.alert("专线数据加载失败，请检查后端服务和数据库连接。");
    }
  });

  els.lineFilterForm.addEventListener("reset", () => {
    window.setTimeout(async () => {
      state.line.filters = {};
      state.line.page = 1;
      state.line.activeSourceType = "";
      try {
        await fetchLines();
      } catch (error) {
        console.error(error);
      }
    }, 0);
  });

  els.linePrevBtn.addEventListener("click", async () => {
    if (state.line.page <= 1) return;
    state.line.page -= 1;
    await fetchLines();
  });

  els.lineNextBtn.addEventListener("click", async () => {
    const totalPages = Math.max(1, Math.ceil(state.line.total / state.line.size));
    if (state.line.page >= totalPages) return;
    state.line.page += 1;
    await fetchLines();
  });

  els.lineTableBody.addEventListener("click", async (event) => {
    const button = event.target.closest(".js-line-detail");
    if (!button) return;
    const id = Number(button.dataset.id);
    if (Number.isNaN(id)) return;
    try {
      await openLineDetail(id);
    } catch (error) {
      console.error(error);
      window.alert("加载专线详情失败。");
    }
  });

  els.lineExportBtn.addEventListener("click", async () => {
    try {
      await exportLines();
    } catch (error) {
      console.error(error);
      window.alert("导出专线数据失败。");
    }
  });
}

function bindOnuEvents() {
  els.onuFilterForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(els.onuFilterForm);
    const filters = {};
    formData.forEach((value, key) => {
      const text = String(value).trim();
      if (text) filters[key] = text;
    });
    state.onu.filters = filters;
    state.onu.page = 1;
    try {
      await fetchOnu();
    } catch (error) {
      console.error(error);
      window.alert("ONU数据加载失败，请检查后端服务和数据库连接。");
    }
  });

  els.onuFilterForm.addEventListener("reset", () => {
    window.setTimeout(async () => {
      state.onu.filters = {};
      state.onu.page = 1;
      try {
        await fetchOnu();
      } catch (error) {
        console.error(error);
      }
    }, 0);
  });

  els.onuPrevBtn.addEventListener("click", async () => {
    if (state.onu.page <= 1) return;
    state.onu.page -= 1;
    await fetchOnu();
  });

  els.onuNextBtn.addEventListener("click", async () => {
    const totalPages = Math.max(1, Math.ceil(state.onu.total / state.onu.size));
    if (state.onu.page >= totalPages) return;
    state.onu.page += 1;
    await fetchOnu();
  });

  els.onuTableBody.addEventListener("click", async (event) => {
    const button = event.target.closest(".js-onu-detail");
    if (!button) return;
    const id = Number(button.dataset.id);
    if (Number.isNaN(id)) return;
    try {
      await openOnuDetail(id);
    } catch (error) {
      console.error(error);
      window.alert("加载ONU详情失败。");
    }
  });

  els.onuExportBtn.addEventListener("click", async () => {
    try {
      await exportOnu();
    } catch (error) {
      console.error(error);
      window.alert("导出ONU数据失败。");
    }
  });
}

function bindBatchEvents() {
  els.batchRefreshBtn.addEventListener("click", async () => {
    try {
      await fetchBatches();
      await refreshDashboard();
    } catch (error) {
      console.error(error);
      window.alert("批次数据加载失败。");
    }
  });
}

function bindAdminDataEvents() {
  els.adminDataRefreshBtn.addEventListener("click", async () => {
    await refreshAdminDataModule();
  });

  els.adminDryRunBtn.addEventListener("click", async () => {
    await runImport(true);
  });

  els.adminImportBtn.addEventListener("click", async () => {
    await runImport(false);
  });

  els.importErrorRefreshBtn.addEventListener("click", async () => {
    try {
      await fetchImportErrors();
    } catch (error) {
      console.error(error);
      setInlineStatus(els.adminImportStatus, "异常列表加载失败", true);
    }
  });

  els.adminLogRefreshBtn.addEventListener("click", async () => {
    try {
      await fetchAdminLogs();
      setInlineStatus(els.adminImportStatus, "操作日志已刷新");
    } catch (error) {
      console.error(error);
      setInlineStatus(els.adminImportStatus, "操作日志加载失败", true);
    }
  });
}

function bindUserEvents() {
  els.userRefreshBtn.addEventListener("click", async () => {
    try {
      await refreshAdminUsersModule();
      setInlineStatus(els.userActionStatus, "用户和会话列表已刷新");
    } catch (error) {
      console.error(error);
      setInlineStatus(els.userActionStatus, "用户列表刷新失败", true);
    }
  });

  els.userCreateForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(els.userCreateForm);
    const payload = {
      username: String(formData.get("username") || "").trim(),
      display_name: String(formData.get("display_name") || "").trim(),
      role: String(formData.get("role") || "").trim(),
      password: String(formData.get("password") || ""),
    };

    if (!payload.username || !payload.display_name || !payload.role || !payload.password) {
      setInlineStatus(els.userActionStatus, "请完整填写新用户信息", true);
      return;
    }

    try {
      const user = await createUser(payload);
      setInlineStatus(els.userActionStatus, `用户 ${user.username} 已创建`);
      els.userCreateForm.reset();
      renderCreateRoleOptions();
      await refreshAdminUsersModule();
      await Promise.all([fetchAdminDataSummary(), fetchAdminLogs()]);
    } catch (error) {
      console.error(error);
      setInlineStatus(els.userActionStatus, `创建失败：${error.message}`, true);
    }
  });

  els.sessionUserFilter.addEventListener("change", async (event) => {
    state.admin.sessionUserId = String(event.target.value || "");
    try {
      await fetchAdminSessions();
    } catch (error) {
      console.error(error);
      setInlineStatus(els.userActionStatus, "会话筛选失败", true);
    }
  });

  els.sessionRefreshBtn.addEventListener("click", async () => {
    try {
      await fetchAdminSessions();
      setInlineStatus(els.userActionStatus, "会话列表已刷新");
    } catch (error) {
      console.error(error);
      setInlineStatus(els.userActionStatus, "会话列表刷新失败", true);
    }
  });

  els.userTableBody.addEventListener("click", async (event) => {
    const row = event.target.closest("tr[data-user-id]");
    if (!row) return;
    const userId = Number(row.dataset.userId);
    if (Number.isNaN(userId)) return;

    if (event.target.closest(".js-user-save")) {
      const displayName = row.querySelector(".js-user-display-name")?.value.trim() || "";
      const role = row.querySelector(".js-user-role")?.value || "";
      if (!displayName || !role) {
        setInlineStatus(els.userActionStatus, "显示名称和角色不能为空", true);
        return;
      }
      try {
        const user = await saveUser(userId, displayName, role);
        setInlineStatus(els.userActionStatus, `用户 ${user.username} 已更新`);
        await refreshAdminUsersModule();
        await fetchAdminLogs();
        if (userId === Number(state.auth.user?.id || 0)) {
          await refreshCurrentUser();
        }
      } catch (error) {
        console.error(error);
        setInlineStatus(els.userActionStatus, `更新失败：${error.message}`, true);
      }
      return;
    }

    if (event.target.closest(".js-user-toggle")) {
      const nextActive = row.dataset.active !== "1";
      try {
        const user = await toggleUser(userId, nextActive);
        setInlineStatus(els.userActionStatus, `用户 ${user.username} 状态已更新`);
        await refreshAdminUsersModule();
        await Promise.all([fetchAdminDataSummary(), fetchAdminLogs()]);
      } catch (error) {
        console.error(error);
        setInlineStatus(els.userActionStatus, `状态更新失败：${error.message}`, true);
      }
      return;
    }

    if (event.target.closest(".js-user-reset")) {
      const password = window.prompt("请输入新的临时密码（至少 12 位）", "");
      if (password === null) return;
      if (String(password).length < 12) {
        setInlineStatus(els.userActionStatus, "密码长度不能少于 6 位", true);
        return;
      }
      try {
        await resetUserPassword(userId, String(password));
        setInlineStatus(els.userActionStatus, `用户 #${userId} 密码已重置`);
        await refreshAdminUsersModule();
        await Promise.all([fetchAdminLogs(), fetchAdminDataSummary()]);
      } catch (error) {
        console.error(error);
        setInlineStatus(els.userActionStatus, `密码重置失败：${error.message}`, true);
      }
      return;
    }

    if (event.target.closest(".js-user-revoke-all")) {
      const confirmed = window.confirm("确认强制下线该用户的全部其他会话？");
      if (!confirmed) return;
      try {
        const data = await revokeUserSessions(userId, "后台管理员强制下线");
        setInlineStatus(els.userActionStatus, `已下线 ${data.revoked || 0} 个会话`);
        await refreshAdminUsersModule();
        await Promise.all([fetchAdminDataSummary(), fetchAdminLogs()]);
      } catch (error) {
        console.error(error);
        setInlineStatus(els.userActionStatus, `强制下线失败：${error.message}`, true);
      }
      return;
    }

    if (event.target.closest(".js-user-delete")) {
      const username = row.querySelector(".mono")?.textContent?.trim() || `#${userId}`;
      const confirmed = window.confirm(`确认删除用户 ${username}？此操作不可恢复。`);
      if (!confirmed) return;
      try {
        await deleteUser(userId);
        setInlineStatus(els.userActionStatus, `用户 ${username} 已删除`);
        await refreshAdminUsersModule();
        await Promise.all([fetchAdminDataSummary(), fetchAdminLogs()]);
      } catch (error) {
        console.error(error);
        setInlineStatus(els.userActionStatus, `删除失败：${error.message}`, true);
      }
    }
  });

  els.sessionTableBody.addEventListener("click", async (event) => {
    const button = event.target.closest(".js-session-revoke");
    if (!button) return;
    const row = event.target.closest("tr[data-session-id]");
    if (!row) return;
    const sessionId = Number(row.dataset.sessionId);
    if (Number.isNaN(sessionId)) return;
    if (!window.confirm(`确认强制下线会话 #${sessionId}？`)) return;

    try {
      await revokeSessionById(sessionId, "后台管理员强制下线");
      setInlineStatus(els.userActionStatus, `会话 #${sessionId} 已下线`);
      await refreshAdminUsersModule();
      await Promise.all([fetchAdminDataSummary(), fetchAdminLogs()]);
    } catch (error) {
      console.error(error);
      setInlineStatus(els.userActionStatus, `会话下线失败：${error.message}`, true);
    }
  });
}

function bindDrawerEvents() {
  els.drawerCloseBtn.addEventListener("click", closeDrawer);
  document.querySelector("[data-close-drawer='true']").addEventListener("click", closeDrawer);
}

async function bootstrapAfterLogin() {
  if (!hasPermission("data.query")) {
    window.alert("当前账号缺少查询权限，请联系管理员分配角色。");
    return;
  }

  updateAuthUI();
  if (PREVIEW_MODE && PREVIEW_INITIAL_MODULE) {
    state.module = PREVIEW_INITIAL_MODULE;
  }
  if (PREVIEW_MODE && PREVIEW_LINE_SOURCE_TYPE) {
    state.line.filters = { ...state.line.filters, source_type: PREVIEW_LINE_SOURCE_TYPE };
    state.line.activeSourceType = PREVIEW_LINE_SOURCE_TYPE;
    if (els.lineFilterForm?.elements?.namedItem("source_type")) {
      els.lineFilterForm.elements.namedItem("source_type").value = PREVIEW_LINE_SOURCE_TYPE;
    }
  }
  if (PREVIEW_MODE && PREVIEW_ONU_SERVICE_TYPE) {
    state.onu.filters = { ...state.onu.filters, service_type: PREVIEW_ONU_SERVICE_TYPE };
    if (els.onuFilterForm?.elements?.namedItem("service_type")) {
      els.onuFilterForm.elements.namedItem("service_type").value = PREVIEW_ONU_SERVICE_TYPE;
    }
  }
  if (isAdmin()) {
    await Promise.all([refreshAdminUsersModule(), fetchAdminDataSummary(), fetchImportErrors(), fetchAdminLogs()]);
  }
  await refreshDashboard();

  const nextModule = isAdmin() ? state.module : ["adminData", "users"].includes(state.module) ? "lines" : state.module;
  await switchModule(nextModule);
}

async function tryRestoreSession() {
  if (PREVIEW_MODE) {
    setSession("preview-token", previewUser);
    hideAuthGate();
    await bootstrapAfterLogin();
    return;
  }
  const token = window.localStorage.getItem(TOKEN_STORAGE_KEY);
  if (!token) {
    showAuthGate("请输入账号密码登录");
    return;
  }

  saveToken(token);
  try {
    const data = await requestJSON("/api/auth/me");
    setSession(token, data.user);
    hideAuthGate();
    await bootstrapAfterLogin();
  } catch (error) {
    console.error(error);
    clearSession();
    showAuthGate("登录已失效，请重新登录");
  }
}

async function login(username, password) {
  if (PREVIEW_MODE) {
    setSession("preview-token", previewUser);
    hideAuthGate();
    await bootstrapAfterLogin();
    return;
  }
  const data = await requestJSON("/api/auth/login", {
    method: "POST",
    body: { username, password },
    auth: false,
  });
  setSession(data.access_token, data.user);
  hideAuthGate();
  await bootstrapAfterLogin();
}

async function logout() {
  if (PREVIEW_MODE) {
    setSession("preview-token", previewUser);
    hideAuthGate();
    await switchModule(state.module || "lines");
    return;
  }
  try {
    if (state.auth.token) {
      await requestJSON("/api/auth/logout", { method: "POST" });
    }
  } catch (error) {
    console.error(error);
  }
  clearSession();
  showAuthGate("已退出登录");
}

function bindAuthEvents() {
  els.loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(els.loginForm);
    const username = String(formData.get("username") || "").trim();
    const password = String(formData.get("password") || "");

    if (!username || !password) {
      els.loginError.textContent = "请输入用户名和密码";
      return;
    }

    els.loginError.textContent = "登录中...";
    try {
      await login(username, password);
      els.loginForm.reset();
    } catch (error) {
      console.error(error);
      els.loginError.textContent = "登录失败，请检查用户名或密码";
    }
  });

  els.logoutBtn.addEventListener("click", async () => {
    await logout();
  });
}

function bindGlobalEvents() {
  els.refreshDashboardBtn.addEventListener("click", async () => {
    await refreshDashboard();
    if (isAdmin() && state.module === "adminData") {
      await refreshAdminDataModule();
    }
    if (isAdmin() && state.module === "users") {
      await refreshAdminUsersModule();
    }
  });
}

async function init() {
  updateDateText();
  updateAuthUI();
  renderCreateRoleOptions();
  window.setInterval(updateDateText, 1000 * 30);

  bindModuleSwitcher();
  bindLineEvents();
  bindOnuEvents();
  bindBatchEvents();
  bindAdminDataEvents();
  bindUserEvents();
  bindDrawerEvents();
  bindAuthEvents();
  bindGlobalEvents();

  await tryRestoreSession();
}

init();
