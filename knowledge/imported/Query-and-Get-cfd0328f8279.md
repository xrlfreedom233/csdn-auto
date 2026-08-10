<!-- source: https://docs.trychroma.com/docs/querying-collections/query-and-get -->
<!-- imported_at: 2026-08-10T14:11:06.741378+08:00 -->

# Query and Get

Querying Collections

Copy page

Learn how to query and retrieve data from Chroma collections.

Copy page

The Query API enables nearest-neighbor similarity search over dense embeddings.
Use the Get API when you want to retrieve records without similarity ranking.

- Python
- TypeScript
- Rust

## [​](#query) Query

You can query a collection to run a similarity search using `.query`:

```
collection.query(
    query_texts=["thus spake zarathustra", "the oracle speaks"]
)
```

Chroma will use the collection’s [embedding function](../embeddings/embedding-functions) to embed your text queries, and use the output to run a vector similarity search against your collection.Instead of providing `query_texts`, you can provide `query_embeddings` directly. You will be required to do so if your collection does not have an embedding function attached to it. The dimension of your query embedding must match the dimension of the embeddings in your collection.Python also supports `query_images` and `query_uris` as query inputs.

```
collection.query(
    query_embeddings=[[11.1, 12.1, 13.1], [1.1, 2.3, 3.2]]
)
```

By default, Chroma will return 10 results per input query. You can modify this number using the `n_results` argument:

```
collection.query(
    query_embeddings=[[11.1, 12.1, 13.1], [1.1, 2.3, 3.2]],
    n_results=100
)
```

The `ids` argument lets you constrain the search only to records with the IDs from the provided list:

```
collection.query(
    query_embeddings=[[11.1, 12.1, 13.1], [1.1, 2.3, 3.2]],
    n_results=100,
    ids=["id1", "id2"]
)
```

Both `query` and `get` support `where` for [metadata filtering](./metadata-filtering) and `where_document` for [full-text search and regex](./full-text-search):

```
collection.query(
    query_embeddings=[[11.1, 12.1, 13.1], [1.1, 2.3, 3.2]],
    n_results=100,
    where={"page": 10}, # query records with metadata field 'page' equal to 10
    where_document={"$contains": "search string"} # query records with the search string in the records' document
)
```

## [​](#get) Get

Use `.get` to retrieve records by ID and/or filters without similarity ranking:

```
collection.get(ids=["id1", "id2"]) # by IDs

collection.get(limit=100, offset=0) # with pagination
```

## [​](#query-2) Query

You can query a collection to run a similarity search using `.query`:

```
await collection.query({
  queryTexts: ["thus spake zarathustra", "the oracle speaks"],
});
```

Chroma will use the collection’s [embedding function](../embeddings/embedding-functions) to embed your text queries, and use the output to run a vector similarity search against your collection.Instead of providing `queryTexts`, you can provide `queryEmbeddings` directly. You will be required to do so if your collection does not have an embedding function attached to it. The dimension of your query embedding must match the dimension of the embeddings in your collection.

```
await collection.query({
  queryEmbeddings: [
    [11.1, 12.1, 13.1],
    [1.1, 2.3, 3.2],
  ],
});
```

By default, Chroma will return 10 results per input query. You can modify this number using the `nResults` argument:

```
await collection.query({
  queryEmbeddings: [
    [11.1, 12.1, 13.1],
    [1.1, 2.3, 3.2],
  ],
  nResults: 100,
});
```

The `ids` argument lets you constrain the search only to records with the IDs from the provided list:

```
await collection.query({
  queryEmbeddings: [
    [11.1, 12.1, 13.1],
    [1.1, 2.3, 3.2],
  ],
  nResults: 100,
  ids: ["id1", "id2"],
});
```

Both `query` and `get` support `where` for [metadata filtering](./metadata-filtering) and `whereDocument` for [full-text search and regex](./full-text-search):

```
await collection.query({
  queryEmbeddings: [
    [11.1, 12.1, 13.1],
    [1.1, 2.3, 3.2],
  ],
  nResults: 5,
  where: { page: 10 }, // metadata field 'page' equal to 10
  whereDocument: { $contains: "search string" }, // documents containing "search string"
});
```

## [​](#get-2) Get

Use `.get` to retrieve records by ID and/or filters without similarity ranking:

```
await collection.get({ ids: ["id1", "id2"] }); // By IDs

await collection.get({ limit: 100, offset: 0 }); // With pagination
```

## [​](#type-inference) Type inference

You can also pass type arguments to `.get` and `.query` for the shape of your metadata. This gives you type inference for your metadata objects:

```
const results = await collection.get<{page: number; title: string}>({
  ids: ["id1", "id2"],
});

const rows = results.rows();
rows.forEach((row) => {
  console.log(row.id, row.metadata?.page);
});
```

## [​](#query-3) Query

You can query a collection to run a similarity search using `.query`:

```
use chroma_types::IncludeList;

// pub async fn query(
//    &self,
//    query_embeddings: Vec<Vec<f32>>,
//    n_results: Option<u32>,
//    where: Option<Where>,
//    ids: Option<Vec<String>>,
//    include: Option<IncludeList>,
// ) -> Result<QueryResponse, ChromaHttpClientError>

let results = collection
    .query(
        vec![vec![11.1, 12.1, 13.1], vec![1.1, 2.3, 3.2]],
        None,
        None,
        None,
        None,
    )
    .await?;
```

Embeddings must be provided directly to the Rust client.By default, Chroma returns 10 results per input query. You can modify this number using `n_results`:

```
let results = collection
    .query(
        vec![vec![11.1, 12.1, 13.1], vec![1.1, 2.3, 3.2]],
        Some(100), // n_results
        None,
        None,
        None,
    )
    .await?;
```

The `ids` argument lets you constrain the search only to records with the IDs from the provided list:

```
let results = collection
    .query(
        vec![vec![11.1, 12.1, 13.1], vec![1.1, 2.3, 3.2]],
        Some(5),
        None,
        Some(vec!["id1".to_string(), "id2".to_string()]), // ids
        None,
    )
    .await?;
```

## [​](#get-3) Get

Use `.get` to retrieve records by ID and/or filters without similarity ranking:

```
let response = collection
    .get(
        Some(vec!["id1".to_string(), "id2".to_string()]),
        None,
        Some(10),
        Some(0),
        Some(IncludeList::default_get()),
    )
    .await?;
```

## [​](#results-shape) Results Shape

Chroma returns `.query` and `.get` results in **column-major** form (arrays per field). `.query` results are grouped per input query; `.get` results are a flat list of records.

Python

TypeScript

Rust

```
class QueryResult(TypedDict):
    ids: List[IDs]
    embeddings: Optional[List[Embeddings]]
    documents: Optional[List[List[Document]]]
    uris: Optional[List[List[URI]]]
    metadatas: Optional[List[List[Metadata]]]
    distances: Optional[List[List[float]]]
    included: Include

class GetResult(TypedDict):
    ids: List[ID]
    embeddings: Optional[Embeddings]
    documents: Optional[List[Document]]
    uris: Optional[URIs]
    metadatas: Optional[List[Metadata]]
    included: Include
```

```
class QueryResult {
  public readonly ids: string[][];
  public readonly distances: (number | null)[][];
  public readonly documents: (string | null)[][];
  public readonly embeddings: (number[] | null)[][];
  public readonly metadatas: (Record<string, string | number | boolean> | null)[][];
  public readonly uris: (string | null)[][];
  public readonly include: Include[];
}

class GetResult {
  public readonly ids: string[];
  public readonly documents: (string | null)[];
  public readonly embeddings: number[][];
  public readonly metadatas: (Record<string, string | number | boolean> | null)[];
  public readonly uris: (string | null)[];
  public readonly include: Include[];
}
```

```
pub struct QueryResponse {
    pub ids: Vec<Vec<String>>,
    pub embeddings: Option<Vec<Vec<Option<Vec<f32>>>>>,
    pub documents: Option<Vec<Vec<Option<String>>>>,
    pub uris: Option<Vec<Vec<Option<String>>>>,
    pub metadatas: Option<Vec<Vec<Option<HashMap<String, MetadataValue>>>>>,
    pub distances: Option<Vec<Vec<Option<f32>>>>,
    pub include: Vec<Include>,
}

pub struct GetResponse {
    pub ids: Vec<String>,
    pub embeddings: Option<Vec<Vec<f32>>>,
    pub documents: Option<Vec<Option<String>>>,
    pub uris: Option<Vec<Option<String>>>,
    pub metadatas: Option<Vec<Option<HashMap<String, MetadataValue>>>>,
    pub include: Vec<Include>,
}
```

Here is a concrete example of what these responses look like in practice:

```
// Query result
{
  "ids": [["doc_1", "doc_7"]],
  "embeddings": [[[1, 2, 3, 4], [1, 2, 3, 4]]],
  "documents": [["Chroma stores vectors.", "Embeddings power semantic search."]],
  "metadatas": [[
    {"source": "docs", "topic": "intro"},
    {"source": "blog", "topic": "search"}
  ]],
  "distances": [[0.12, 0.21]],
  "included": ["embeddings", "documents", "metadatas", "distances"]
}
// Get result
{
  "ids": ["doc_1", "doc_7"],
  "embeddings": [[1, 2, 3, 4], [1, 2, 3, 4]],
  "documents": ["Chroma stores vectors.", "Embeddings power semantic search."],
  "metadatas": [
    {"source": "docs", "topic": "intro"},
    {"source": "blog", "topic": "search"}
  ],
  "included": ["documents", "metadatas"]
}
```

In the results from the Get operation, corresponding elements in each array belong
to the same document.

Python

TypeScript

Rust

```
result = collection.get(include=["documents", "metadatas"])
for id, document, metadata in zip(result["ids"], result["documents"], result["metadatas"]):
    print(id, document, metadata)
```

```
const result = await collection.get();

const first_document = {
    id: result["ids"][0],
    document: result["documents"][0],
    metadatas: result["metadatas"][0]
}

// Use the .rows() function for easy iteration
for (const row of result.rows()) {
  console.log(row.id, row.document, row.metadata);
}
```

```
let result = collection.get(None, None, None, None, None).await?;
if let (Some(documents), Some(metadatas)) = (&result.documents, &result.metadatas) {
    for i in 0..result.ids.len() {
        let id = &result.ids[i];
        let document = &documents[i];
        let metadata = &metadatas[i];
        println!("{id:?} {document:?} {metadata:?}");
    }
}
```

Query is a batch API and returns results grouped per input. A common pattern is to iterate over each query’s “batch” of results, then iterate within that batch.

Python

TypeScript

Rust

```
result = collection.query(query_texts=["first query", "second query"])
for ids, documents, metadatas in zip(result["ids"], result["documents"], result["metadatas"]):
    for id, document, metadata in zip(ids, documents, metadatas):
        print(id, document, metadata)
```

```
const result = await collection.query({ queryTexts: ["first query", "second query"] });
for (const batch of result.rows()) {
  for (const row of batch) {
    console.log(row.id, row.document, row.metadata, row.distance);
  }
}
```

```
let result = collection
    .query(vec![vec![0.1, 0.2, 0.3]], None, None, None, None)
    .await?;

if let (Some(doc_batches), Some(meta_batches)) = (&result.documents, &result.metadatas) {
    for batch_i in 0..result.ids.len() {
        let ids = &result.ids[batch_i];
        let documents = &doc_batches[batch_i];
        let metadatas = &meta_batches[batch_i];
        for j in 0..ids.len() {
            let id = &ids[j];
            let document = &documents[j];
            let metadata = &metadatas[j];
            println!("{id:?} {document:?} {metadata:?}");
        }
    }
}
```

## [​](#choosing-which-data-is-returned) Choosing Which Data is Returned

By default, Query returns `documents`, `metadatas`, and `distances`, and Get returns `documents` and `metadatas`.
Use `include` to control what comes back. `ids` are always returned.

Python

TypeScript

Rust

```
collection.query(
    query_texts=["my query"],
    include=["documents", "metadatas", "embeddings"],
)

collection.get(include=["documents"])
```

```
await collection.query({
  queryTexts: ["my query"],
  include: ["documents", "metadatas", "embeddings"],
});

await collection.get({ include: ["documents"] });
```

```
use chroma_types::{Include, IncludeList};

let include = IncludeList(vec![Include::Document, Include::Metadata]);

let results = collection
    .query(vec![vec![0.1, 0.2, 0.3]], Some(5), None, None, Some(include))
    .await?;
```

Was this page helpful?

YesNo

[Suggest edits](https://github.com/chroma-core/chroma/edit/main/docs/mintlify/docs/querying-collections/query-and-get.mdx)

⌘I
