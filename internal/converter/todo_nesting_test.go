package converter

import (
	"fmt"
	"strings"
	"testing"

	larkdocx "github.com/larksuite/oapi-sdk-go/v3/service/docx/v1"
)

// TestTodoNestedChildren_Import 验证 todo 列表项的嵌套子项在导入时能正确收集
func TestTodoNestedChildren_Import(t *testing.T) {
	md := `- [ ] 父任务
    - [ ] 子任务1
    - [ ] 子任务2
- [ ] 独立任务`

	conv := NewMarkdownToBlock([]byte(md), ConvertOptions{}, "")
	result, err := conv.ConvertWithTableData()
	if err != nil {
		t.Fatalf("ConvertWithTableData 失败: %v", err)
	}

	// 应该有 2 个顶层块: 父任务, 独立任务
	if len(result.BlockNodes) != 2 {
		t.Fatalf("期望 2 个顶层块，得到 %d", len(result.BlockNodes))
	}

	// 第一个块（父任务）应该有 2 个子项（子任务1, 子任务2）
	parent := result.BlockNodes[0]
	if len(parent.Children) != 2 {
		t.Errorf("'父任务' 期望 2 个子项，得到 %d", len(parent.Children))
	}

	// 验证子项都是 Todo 类型
	for i, child := range parent.Children {
		if child.Block.BlockType == nil || *child.Block.BlockType != int(BlockTypeTodo) {
			bt := 0
			if child.Block.BlockType != nil {
				bt = *child.Block.BlockType
			}
			t.Errorf("子项 %d 期望类型 %d (Todo)，得到 %d", i, BlockTypeTodo, bt)
		}
	}

	// 第二个块（独立任务）不应有子项
	if len(result.BlockNodes[1].Children) != 0 {
		t.Errorf("'独立任务' 不应有子项，得到 %d", len(result.BlockNodes[1].Children))
	}
}

// TestTodoNestedChildren_Export 验证 todo 嵌套子项在导出时正确缩进
func TestTodoNestedChildren_Export(t *testing.T) {
	falseVal := false
	blocks := []*larkdocx.Block{
		{
			BlockId:   strPtr("parent"),
			BlockType: intPtr(int(BlockTypeTodo)),
			Children:  []string{"child1", "child2"},
			Todo: &larkdocx.Text{
				Elements: []*larkdocx.TextElement{
					{TextRun: &larkdocx.TextRun{Content: strPtr("父任务")}},
				},
				Style: &larkdocx.TextStyle{Done: &falseVal},
			},
		},
		{
			BlockId:   strPtr("child1"),
			BlockType: intPtr(int(BlockTypeTodo)),
			Todo: &larkdocx.Text{
				Elements: []*larkdocx.TextElement{
					{TextRun: &larkdocx.TextRun{Content: strPtr("子任务1")}},
				},
				Style: &larkdocx.TextStyle{Done: &falseVal},
			},
		},
		{
			BlockId:   strPtr("child2"),
			BlockType: intPtr(int(BlockTypeTodo)),
			Todo: &larkdocx.Text{
				Elements: []*larkdocx.TextElement{
					{TextRun: &larkdocx.TextRun{Content: strPtr("子任务2")}},
				},
				Style: &larkdocx.TextStyle{Done: &falseVal},
			},
		},
	}

	conv := NewBlockToMarkdown(blocks, ConvertOptions{})
	got, err := conv.Convert()
	if err != nil {
		t.Fatalf("Convert() error = %v", err)
	}
	got = strings.TrimSpace(got)

	want := "- [ ] 父任务\n  - [ ] 子任务1\n  - [ ] 子任务2"
	if got != want {
		t.Errorf("Convert() got:\n%s\n\nwant:\n%s", got, want)
	}
}

// TestTodoNestedChildren_Roundtrip 验证 todo 嵌套子项的往返一致性
func TestTodoNestedChildren_Roundtrip(t *testing.T) {
	md := `- [ ] 父任务
  - [ ] 子任务1
  - [x] 子任务2`

	// Markdown → Block
	conv := NewMarkdownToBlock([]byte(md), ConvertOptions{}, "")
	result, err := conv.ConvertWithTableData()
	if err != nil {
		t.Fatalf("Markdown → Block 失败: %v", err)
	}

	// 构建带 ID 和 Children 关系的 Block 切片（模拟飞书 API 返回的结构）
	var allBlocks []*larkdocx.Block
	idCounter := 0
	var assignIDs func(nodes []*BlockNode) []string
	assignIDs = func(nodes []*BlockNode) []string {
		var ids []string
		for _, n := range nodes {
			idCounter++
			id := fmt.Sprintf("blk_%d", idCounter)
			n.Block.BlockId = &id
			// 递归处理子节点
			childIDs := assignIDs(n.Children)
			if len(childIDs) > 0 {
				n.Block.Children = childIDs
			}
			allBlocks = append(allBlocks, n.Block)
			ids = append(ids, id)
		}
		return ids
	}
	assignIDs(result.BlockNodes)

	// Block → Markdown
	conv2 := NewBlockToMarkdown(allBlocks, ConvertOptions{})
	got, err := conv2.Convert()
	if err != nil {
		t.Fatalf("Block → Markdown 失败: %v", err)
	}
	got = strings.TrimSpace(got)

	want := "- [ ] 父任务\n  - [ ] 子任务1\n  - [x] 子任务2"
	if got != want {
		t.Errorf("往返不一致:\n  输入: %q\n  输出: %q", want, got)
	}
}
