
import http from 'k6/http';
import { check } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

// Variant B: API ingress metrics.
// These metrics measure acceptance, NOT completed Worker processing.
const apiProcessingTime = new Trend('variant_b_api_processing_time_ms');
const acceptedTransactions = new Counter('variant_b_accepted_transactions');
const ingressSuccessRate = new Rate('variant_b_ingress_success_rate');

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const TOKEN = __ENV.K6_TOKEN;

const RATE = Number(__ENV.RATE || 10);
const DURATION = __ENV.DURATION || '30s';

export const options = {
    scenarios: {
        transaction_ingestion: {
            executor: 'constant-arrival-rate',
            rate: RATE,
            timeUnit: '1s',
            duration: DURATION,
            preAllocatedVUs: 200,
            maxVUs: 250,
        },
    },
};

export default function () {
    if (!TOKEN) {
        throw new Error('K6_TOKEN environment variable is missing');
    }

    const uniqueId = `k6-b-${__VU}-${__ITER}-${Date.now()}`;

    const payload = JSON.stringify({
        transaction_id: uniqueId,
        amount: 299.99,
        currency: 'USD',
        transaction_type: 'PAYMENT',
        customer_id: '987e6543-e21a-12d3-a456-426614174111',
        payment_method: 'CARD',
        transaction_time: new Date().toISOString(),
    });

    const response = http.post(
        `${BASE_URL}/api/v1/transactions/ingest`,
        payload,
        {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${TOKEN}`,
            },
            tags: {
                endpoint: 'transaction_ingest',
                architecture: 'variant_b',
            },
        }
    );

    const success = check(response, {
        'status is 202': (r) => r.status === 202,
        'response contains transaction_id': (r) => {
            try {
                return Boolean(r.json('transaction_id'));
            } catch (_) {
                return false;
            }
        },
    });

    ingressSuccessRate.add(success);

    if (success) {
        acceptedTransactions.add(1);

        try {
            const processingTime = response.json('processing_time_ms');

            if (processingTime !== undefined && processingTime !== null) {
                apiProcessingTime.add(Number(processingTime));
            }
        } catch (_) {
            // Ignore invalid response bodies.
        }
    }
}
