# 14 Archive Engine / 统一档案引擎

## 适用模块

- 门店
- 员工
- 品牌
- 产品
- 供应商
- 顾客/会员

## 统一能力

- 新建
- 编辑
- 删除
- 详情页
- 搜索
- 标签
- 备注
- 时间轴
- 关联对象
- 附件
- 上传图片、PDF、Word、Excel、视频
- 自动归档占位
- AI 查询占位
- 全文搜索占位

## Task008 Graph Integration

Archive records can become graph entities. Explicit fields may create safe relationships:

- Employee works_at Store
- Product belongs_to Brand
- Supplier supplies Brand
- Customer purchased Product

Only explicit fields or user selections can create graph relationships.
