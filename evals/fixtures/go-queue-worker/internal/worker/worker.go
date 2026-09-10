package worker

import (
	"go-queue-worker/internal/cache"
)

type Job struct {
	ID      string
	Payload string
}

// Run starts N goroutines pulling from the internal jobs channel.
// Internal-only service: no external HTTP endpoint, no auth layer, consumes
// from a private queue populated by another internal service.
func Run(jobs <-chan Job, concurrency int) {
	for i := 0; i < concurrency; i++ {
		go func() {
			for job := range jobs {
				process(job)
			}
		}()
	}
}

func process(job Job) {
	cache.SetStatus(job.ID, "processing")
	// ... do work, no timeout on any downstream call, no retry on failure ...
	cache.SetStatus(job.ID, "done")
}
