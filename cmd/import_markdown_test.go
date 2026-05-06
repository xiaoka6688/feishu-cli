package cmd

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	larkdocx "github.com/larksuite/oapi-sdk-go/v3/service/docx/v1"
	"github.com/riba2534/feishu-cli/internal/converter"
)

func TestValidateWorkerCount(t *testing.T) {
	tests := []struct {
		name    string
		value   int
		wantErr bool
	}{
		{name: "positive", value: 1, wantErr: false},
		{name: "zero", value: 0, wantErr: true},
		{name: "negative", value: -1, wantErr: true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validateWorkerCount("image-workers", tt.value)
			if (err != nil) != tt.wantErr {
				t.Fatalf("validateWorkerCount() error = %v, wantErr = %v", err, tt.wantErr)
			}
		})
	}
}

func TestResolveImageSourceLocal(t *testing.T) {
	baseDir := t.TempDir()
	imagePath := filepath.Join(baseDir, "local-image.png")
	if err := os.WriteFile(imagePath, []byte("png"), 0644); err != nil {
		t.Fatalf("write image: %v", err)
	}

	localPath, fileName, cleanup, err := resolveImageSource("local-image.png", baseDir)
	if err != nil {
		t.Fatalf("resolveImageSource() error = %v", err)
	}
	defer cleanup()

	if localPath != imagePath {
		t.Fatalf("localPath = %q, want %q", localPath, imagePath)
	}
	if fileName != "local-image.png" {
		t.Fatalf("fileName = %q, want %q", fileName, "local-image.png")
	}
}

func TestResolveImageSourceHTTPURL(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "image/png")
		_, _ = w.Write([]byte("fake-png-data"))
	}))
	defer srv.Close()

	source := srv.URL + "/nested/logo.png?x=1"
	localPath, fileName, cleanup, err := resolveImageSource(source, "")
	if err != nil {
		t.Fatalf("resolveImageSource() error = %v", err)
	}

	if fileName != "logo.png" {
		t.Fatalf("fileName = %q, want %q", fileName, "logo.png")
	}
	if _, err := os.Stat(localPath); err != nil {
		t.Fatalf("downloaded file missing: %v", err)
	}

	cleanup()
	if _, err := os.Stat(localPath); !os.IsNotExist(err) {
		t.Fatalf("cleanup did not remove temp file, stat err = %v", err)
	}
}

func TestResolveImageSourceHTTPURLWithoutPathName(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "image/png")
		_, _ = w.Write([]byte("fake-png-data"))
	}))
	defer srv.Close()

	localPath, fileName, cleanup, err := resolveImageSource(srv.URL, "")
	if err != nil {
		t.Fatalf("resolveImageSource() error = %v", err)
	}
	defer cleanup()

	if fileName != "image.png" {
		t.Fatalf("fileName = %q, want %q", fileName, "image.png")
	}
	if filepath.Ext(localPath) != ".png" {
		t.Fatalf("temp file ext = %q, want %q", filepath.Ext(localPath), ".png")
	}
}

func TestAppendVideoTasksIncludesNestedVideosInTreeOrder(t *testing.T) {
	topVideo := videoNode("top.mp4")
	grid := &converter.BlockNode{
		Block: blockWithType(converter.BlockTypeGrid),
		Children: []*converter.BlockNode{
			videoNode("nested-a.mp4"),
			{
				Block: blockWithType(converter.BlockTypeQuoteContainer),
				Children: []*converter.BlockNode{
					videoNode("nested-b.mp4"),
				},
			},
		},
	}

	tasks := appendVideoTasks(nil,
		[]*converter.BlockNode{topVideo, grid},
		[]string{"top-id", "grid-id"},
		map[int][]createdBlockNode{
			1: {
				{node: grid.Children[0], blockID: "nested-a-id"},
				{node: grid.Children[1], blockID: "quote-id"},
				{node: grid.Children[1].Children[0], blockID: "nested-b-id"},
			},
		},
		[]string{"./top.mp4", "./nested-a.mp4", "./nested-b.mp4"},
		"/tmp",
	)

	if len(tasks) != 3 {
		t.Fatalf("len(tasks) = %d, want 3", len(tasks))
	}
	wantIDs := []string{"top-id", "nested-a-id", "nested-b-id"}
	wantSources := []string{"./top.mp4", "./nested-a.mp4", "./nested-b.mp4"}
	for i := range tasks {
		if tasks[i].fileBlockID != wantIDs[i] || tasks[i].source != wantSources[i] {
			t.Fatalf("task[%d] = {id:%q source:%q}, want {id:%q source:%q}",
				i, tasks[i].fileBlockID, tasks[i].source, wantIDs[i], wantSources[i])
		}
	}
}

func TestProcessVideoTaskRejectsFilesOverUploadAllLimit(t *testing.T) {
	baseDir := t.TempDir()
	videoPath := filepath.Join(baseDir, "large.mp4")
	f, err := os.Create(videoPath)
	if err != nil {
		t.Fatalf("create video: %v", err)
	}
	if err := f.Truncate(20*1024*1024 + 1); err != nil {
		_ = f.Close()
		t.Fatalf("truncate video: %v", err)
	}
	if err := f.Close(); err != nil {
		t.Fatalf("close video: %v", err)
	}

	result := processVideoTask("doc-token", videoTask{
		index:       1,
		fileBlockID: "block-id",
		source:      "large.mp4",
		basePath:    baseDir,
	}, false, "user-token")

	if result.success {
		t.Fatal("processVideoTask() success = true, want false")
	}
	if result.err == nil || !strings.Contains(result.err.Error(), "视频超过") {
		t.Fatalf("processVideoTask() err = %v, want video size limit error", result.err)
	}
}

func videoNode(name string) *converter.BlockNode {
	blockType := int(converter.BlockTypeFile)
	return &converter.BlockNode{
		Block: &larkdocx.Block{
			BlockType: &blockType,
			File:      &larkdocx.File{Name: &name},
		},
	}
}

func blockWithType(blockType converter.BlockType) *larkdocx.Block {
	bt := int(blockType)
	return &larkdocx.Block{BlockType: &bt}
}
