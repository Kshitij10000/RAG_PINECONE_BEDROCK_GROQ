from langchain_community.document_loaders import TextLoader
from langchain_aws import BedrockEmbeddings
from langchain_text_splitters import CharacterTextSplitter 
from langchain_pinecone import PineconeVectorStore 

loader = TextLoader("grims.txt")
documents = loader.load()
text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
docs = text_splitter.split_documents(documents) 

embeddings = BedrockEmbeddings()
index_name = "rag-aws"
docsearch = PineconeVectorStore.from_documents(docs, embeddings, index_name=index_name) 